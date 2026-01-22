# ComfyUI Workflow CLI Tools

CLI for analyzing and editing ComfyUI workflow JSON files - **always use these tools, never edit JSON manually**.

Workflows are in `workflows/`. Run commands with:
```
python we_vibin.py <command> workflows/example.json [args]
```

## Commands

In the tables below, `WF` = workflow file path.

### Analysis
| Command | Purpose |
|---------|---------|
| `info WF` | Node counts, types summary |
| `analyze WF` | Entry/exit points, pipelines, loops |
| `query WF -t TYPE` | Find nodes by type |
| `trace WF NODE` | Show node inputs/outputs with slot names |
| `values WF NODE` | Show widget values |
| `path WF FROM TO` | Shortest path between nodes |
| `subgraph WF FROM TO` | All nodes/paths between two points |
| `upstream WF NODE [-d DEPTH] [-i INPUT]` | All nodes feeding into target |
| `downstream WF NODE [-d DEPTH] [-O OUTPUT]` | All nodes fed by source |
| `graph WF [-f FILTER]` | List all links (raw) |
| `unconnected WF [--inputs] [--outputs] [-p]` | Unconnected inputs/outputs |
| `verify WF` | Check workflow integrity |
| `diff WF1 WF2` | Compare two workflows |

### Editing (all require `-o output.json`)
| Command | Purpose |
|---------|---------|
| `copy WF NODE -o OUT [-t TITLE] [-s key=val]` | Duplicate node |
| `wire WF SRC_ID SRC_SLOT DST_ID DST_SLOT -o OUT` | Connect nodes |
| `set WF NODE key=val ... -o OUT` | Set widget values |
| `delete WF NODE ... -o OUT [--dry-run] [--cascade]` | Remove nodes |
| `create WF TYPE -o OUT [-t TITLE] [-i in:TYPE] [-O out:TYPE]` | Create new node |
| `inline WF -o OUT [--dry-run]` | Flatten variable references (GetNode/SetNode) |
| `batch WF SCRIPT -o OUT [--dry-run]` | Execute batch script |

### Other
| Command | Purpose |
|---------|---------|
| `visualize WF -o OUT [-g FILE] [--scale F] [--width N] [--no-links]` | Generate SVG diagram |
| `layout WF -o OUT [-g FILE] [-n NODE ...]` | Auto-arrange nodes |
| `fetch WF NODE [-s\|--source] [-f\|--full]` | Fetch node source from GitHub |
| `fetch WF NODE -S TERM` | Search node source for term |

## Batch Scripts

**Use batch scripts for multi-step edits.** Use `--dry-run` to preview.

```bash
# Copy node, assign to variable
copy 1183 as $selector

# Set widgets (key name for dict-style, index for list-style)
set $selector indexes="0:81"
set 577 0=8

# Wire using slot names or numbers (use `trace` to find names)
wire 1140:IMAGE -> $selector:image

# Delete nodes
delete 1220 1228
```

## Example Output

### trace - Find slot names for wiring
```
$ python we_vibin.py trace workflow.json 577
[Node 577] WanVideoSampler

  INPUTS (what feeds into this node):
    [0] model <- [Node 608] GetNode (slot 0)
    [1] image_embeds <- [Node 1179] WanVideoVACEEncode (slot 0)
    ...
  OUTPUTS (what this node feeds into):
    [0] samples -> [Node 595] WanVideoDecode (slot 1)
```

### values - See widget keys for set command
```
$ python we_vibin.py values workflow.json 577
Widget values (list):          # <-- use numeric index
  [0] 6  [1] 1  ...

$ python we_vibin.py values workflow.json 1183
Widget values (dict):          # <-- use key name
  indexes: '-1'
```

## After Completing a Task

**Always look for improvements.** Based on the user's task and any friction encountered:
- Was a command missing or awkward?
- Would a new flag help?
- Was output confusing?

Proactively suggest changes. If the user agrees, implement it immediately. Then push them to contribute - offer to open a PR so others benefit too.
