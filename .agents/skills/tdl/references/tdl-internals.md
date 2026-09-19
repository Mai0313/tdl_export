# tdl v0.20.4 internals

Source citations behind every claim in `SKILL.md`. Read at tag `v0.20.4` (commit `9d7d49e`,
2026-08-23). Line numbers move between releases; the surrounding code is quoted so you can find it
again. Anything marked *measured* was confirmed by running the binary against a real chat.

- [Failure handling](#failure-handling)
- [Temp files and resume](#temp-files-and-resume)
- [--skip-same](#--skip-same)
- [The naming template](#the-naming-template)
- [What counts as media](#what-counts-as-media)
- [The `-f` input parser](#the--f-input-parser)
- [chat export](#chat-export)
- [Cost and rate limits](#cost-and-rate-limits)

## Failure handling

`core/downloader/downloader.go`, inside `Download`:

```go
wg.Go(func() (rerr error) {
    d.opts.Progress.OnAdd(elem)
    defer func() { d.opts.Progress.OnDone(elem, rerr) }()

    if err := d.download(wgctx, elem); err != nil {
        if errors.Is(err, context.Canceled) {
            return errors.Wrap(err, "download")
        }
        // don't return error, just log it
        logctx.From(ctx).Error("Download error", zap.Any("element", elem), zap.Error(err))
    }
    return nil
})
```

`rerr` stays `nil` for every non-cancel error, so `OnDone` receives `nil`. In `app/dl/progress.go`
that is the success branch: `p.it.Finish(...)` then `donePost(e)`, which renames the `.tmp` to the
final name and sets the mtime. The error never reaches the process exit status.

The cancel branch is the only one that cleans up:

```go
if err != nil {
    if !errors.Is(err, context.Canceled) {
        p.fail(t, elem, errors.Wrap(err, "progress"))
    }
    _ = os.Remove(e.to.Name())
    return
}
```

*Measured*: a `SIGTERM` mid-transfer left the `.tmp` on disk, so the cleanup is not reliable under a
hard kill.

Upstream issue #1150 ("files in the JSON never appear, exit 0") is the same symptom in the wild.

## Temp files and resume

`app/dl/iter.go` creates the destination:

```go
const tempExt = ".tmp"
...
filename := fmt.Sprintf("%s%s", toName.String(), tempExt)
path := filepath.Join(i.opts.Dir, filename)
os.MkdirAll(filepath.Dir(path), 0o755)   // #113: a template may contain directories
to, err := os.Create(path)
```

`os.Create` is `O_RDWR|O_CREATE|O_TRUNC`, so a surviving `.tmp` is discarded, not resumed. Parts are
written in parallel with `WriteAt` at arbitrary offsets, so a `.tmp` can also be full-length with
holes — never size-check one.

`app/dl/dl.go` decides whether to prompt:

```go
if !opts.Restart {
    if err = resume(ctx, kvd, it, !opts.Continue); err != nil { return err }
}
...
confirm := false
if ask {
    if err = survey.AskOne(&survey.Confirm{Message: ...}, &confirm); err != nil { return err }
}
```

With neither `--continue` nor `--restart`, `ask` is true and a leftover resume key puts an interactive
prompt on stdin.

The resume record is a bolt key `resume:<sha256>` whose fingerprint covers the exact sorted
`(peer, message ids)` set, holding **logical positions**, not message ids. Adding or removing a single
id invalidates it, and it is deleted on a successful run. It is not a download archive and cannot be
used as one. `--desc` changes every position without changing the fingerprint, which invalidates it
silently.

## --skip-same

`app/dl/iter.go`, in `processSingle`, after the template has been rendered:

```go
if i.opts.SkipSame {
    if stat, err := os.Stat(filepath.Join(i.opts.Dir, toName.String())); err == nil {
        if fsutil.GetNameWithoutExt(toName.String()) == fsutil.GetNameWithoutExt(stat.Name()) &&
            stat.Size() == item.Size {
            return false, true
        }
    }
}
```

The name comparison is a tautology — both sides derive from the same string — so the operative rule is
"the exact rendered path exists and its size matches". The help text's "without extension" is
misleading: the extension had to match for the `Stat` to succeed at all.

*Measured*: an identical 1.8 GB file was skipped instantly; the same file truncated to 100 bytes was
re-downloaded; a copy under the same basename with a different extension was **not** matched.

`--rewrite-ext` renames after download (`donePost` in `app/dl/progress.go` sniffs the MIME and swaps
the extension), which puts the file at a path this `Stat` will never find.

## The naming template

`cmd/dl.go`:

```go
cmd.Flags().String(consts.FlagDlTemplate,
    `{{ .DialogID }}_{{ .MessageID }}_{{ filenamify .FileName }}`,
    "download file name template")
```

Read through viper with `AutomaticEnv` and the `tdl` prefix, so `TDL_TEMPLATE` replaces it when the
flag is absent.

The template struct (`app/dl/iter.go`) has exactly seven fields: `DialogID int64`, `MessageID int`,
`MessageDate int64`, `FileName`, `FileCaption`, `FileSize string`, `DownloadDate int64`. `DialogID` is
`from.ID()` — gotd's `Channel.ID()` returns the raw channel id, so it is positive and carries no
`-100` prefix.

Never put `{{ now }}`, `{{ rand }}` or `{{ .DownloadDate }}` in a template you intend to parse:
`DownloadDate` is `time.Now().Unix()` evaluated per file, so the same message renders a different name
every run.

Custom functions available: `repeat`, `replace`, `upper`, `lower`, `snakecase`, `camelcase`,
`kebabcase`, `filenamify`, `rand`, `now`, `formatDate`. `replace` is `strings.NewReplacer` over
literal pairs, so there is no way to lower-case only the extension inside a template.

`filenamify` (flytam/filenamify) replaces `<>:"/\|?*` and the C0/C1 control ranges with `!`, collapses
repeats, strips leading and trailing `!`, appends `!` to Windows reserved device names, and truncates
to **100 runes including the extension**. It does not touch spaces or CJK.

Default template history: `{{ .DialogID }}_{{ .MessageID }}_{{ .FileName }}` through v0.7.1, a
`replace`-chain form through v0.17.7, and the current `filenamify` form from v0.18.1. The
`<DialogID>_<MessageID>_` prefix is the only part that has never changed.

## What counts as media

`core/tmedia/media.go`:

```go
func ExtractMedia(m tg.MessageMediaClass) (*Media, bool) {
    switch m := m.(type) {
    case *tg.MessageMediaPhoto:    return GetPhotoInfo(m)
    case *tg.MessageMediaDocument: return GetDocumentInfo(m)
    case *tg.MessageMediaInvoice:  return GetExtendedMedia(m.ExtendedMedia)
    }
    return nil, false
}
```

Everything else — web-page previews, paid media, stories, polls, giveaways — is invisible to tdl. So
"the export returned N entries" is never "the chat contains N media items"; the honest claim is
"everything tdl can download".

Names for media that has none of its own are synthesised and stable, which is what makes `--skip-same`
possible at all (upstream #185):

- photo → `<tg.Photo.ID>.jpg`, always `.jpg`, derived from the photo id rather than the message id
- document with no `DocumentAttributeFilename` → `<tg.Document.ID><ext from MIME>`, falling back to
    `.unknown`

Because a photo's name comes from the photo id, the same image forwarded into two chats produces the
same `file` string. Key on `(chat id, message id)`, never on the filename.

Sizes, for the `--raw` path: `Document.Size` for documents; for photos the last entry of
`Photo.Sizes`, reading `.Sizes[-1]` when it is a `PhotoSizeProgressive` and `.Size` otherwise. This
mirrors `GetPhotoSize`, which takes `sizes[len(sizes)-1]`.

## The `-f` input parser

`pkg/tmessage/files.go`. The whole of what it reads:

```go
type fMessage struct {
    ID     int    `mapstructure:"id"`
    Type   string `mapstructure:"type"`
    Time   string `mapstructure:"date_unixtime"`
    File   string `mapstructure:"file"`
    Photo  string `mapstructure:"photo"`
    ...
}
...
if fm.ID < 0 || fm.Type != typeMessage { continue }
if fm.File == "" && fm.Photo == "" && onlyMedia { continue }
m.Messages = append(m.Messages, fm.ID)
```

`onlyMedia` is hardcoded `true` by `app/dl/dl.go`, so text-only entries are dropped during parsing at
no API cost. Decoding is `mapstructure.WeakDecode` with no `ErrorUnused`, so unknown fields are
ignored — extra bookkeeping inside a message object is safe. Note it reads `date_unixtime`, not
`date`, and never uses the value.

The chat id comes from a separate streaming scan that stops at the first depth-1 key named `id`:

```go
if _kv.Key == keyID { chatID = int64(_kv.Value.(float64)) }
```

That type assertion is unchecked, so a string `"id"` panics rather than erroring. And because the scan
materialises each top-level value as it goes, putting `messages` before `id` decodes the entire array
just to find the chat id.

The depth-2 object scan is key-agnostic — any top-level array of objects carrying `id` and
`type: "message"` becomes download targets. There is also no deduplication anywhere, so a repeated id
is fetched twice and written twice to the same path.

## chat export

`app/chat/export.go`. The output struct:

```go
type Message struct {
    ID   int         `json:"id"`
    Type string      `json:"type"`
    File string      `json:"file"`
    Date int         `json:"date,omitempty"`
    Text string      `json:"text,omitempty"`
    Raw  *tg.Message `json:"raw,omitempty"`
}
```

`Date` and `Text` are only populated under `--with-content`; `Raw` only under `--raw`. There is no
size, MIME, media-kind or album field in the plain output. The envelope is written by hand with a
streaming encoder, `id` first, then `messages`.

Selection:

```go
m, ok := msg.Msg.(*tg.Message)
if !ok { continue }                       // service messages are always dropped
media, ok := tmedia.GetMedia(m)
if !ok && !opts.All { continue }
```

So `--all` means "also plain `*tg.Message` without downloadable media", not "literally everything",
and message-id gaps in an export are expected.

Ranges:

```go
case ExportTypeId:
    iter = iter.OffsetID(opts.Input[1] + 1)   // #89: retain the last msg id
...
case ExportTypeId:
    if msg.Msg.GetID() < opts.Input[0] { break loop }
```

Both bounds inclusive. `cmd/chat.go` fills the missing ones:

```go
switch len(opts.Input) {
case 0: opts.Input = []int{0, math.MaxInt}
case 1: opts.Input = append(opts.Input, math.MaxInt)
}
if opts.Input[0] > opts.Input[1] { opts.Input[0], opts.Input[1] = opts.Input[1], opts.Input[0] }
```

so `-T id` alone is a full export and `-T id -i N` is "everything from N up". Out-of-order input is
silently sorted. `-T last -i N` returns the newest N *matching* messages; `-T time` takes unix
timestamps with the same shape.

`--filter` compiles an `expr-lang` expression over the fields `tdl chat export -f -` prints:
`Mentioned, Silent, FromScheduled, Pinned, ID, FromID, Date, Message, Media.Name, Media.Size, Media.DC, Views, Forwards`. *Measured*: `Media.Size > 0` selects media-only without a nil dereference on text
messages.

The command prints its own warning that the output is "minimal JSON for tdl download, not for backup".

## Cost and rate limits

Export iterates with `messages.NewIterator(q, 100)` behind a package-level limiter of 2 requests per
second (burst 2). No flag changes it; `--delay` and `--pool` do not apply. *Measured*: 603 messages in
4.3 s, 4,308 in 45 s, 10,980 in 2 m 10 s.

Download resolves each id separately (`core/util/tutil/tutil.go`):

```go
func GetSingleMessage(ctx context.Context, c *tg.Client, peer tg.InputPeerClass, msg int) (*tg.Message, error) {
    it := query.Messages(c).GetHistory(peer).OffsetID(msg + 1).BatchSize(1).Iter()
```

One round trip per id, serially, before any skip logic runs.

`-l/--limit` is concurrent files (default 2); `-t/--threads` is threads per file (default 4), capped
downward by size. FLOOD_WAIT is absorbed by gotd's waiter with no cap and no message, so a silent
process is usually waiting rather than stuck. `-s/--size` has been a no-op since v0.18.1.

A numeric chat id resolves through `tutil.GetInputPeer` → `manager.ResolveChannelID`, which needs the
access hash from the local peer store at `~/.tdl/data`. On a fresh session that store is empty and the
id alone will not resolve; `tdl chat ls` populates it. Usernames do not have this problem.
