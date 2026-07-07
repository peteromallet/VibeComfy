Canonical delta V2 lives at `{schema_version: "2.0.0", ops: [...]}` and supports
exactly six op types:

- `set_node_field`
- `set_mode`
- `add_node`
- `upsert_link`
- `remove_node`
- `remove_link`

Legacy handling is explicit:

- Flat V2 op arrays are a temporary bridge only when a caller opts in to
  `allow_legacy_list=True`.
- Legacy wrapped delta mappings such as `{"ops": [...], "diagnostics": ...}` or
  `{"delta_ops": ...}` are rejected as `legacy_delta_shape`.
- Canonical add-node entries must carry explicit `uid` and `node_id`; consumers
  must not infer added-node identity from an empty `scope_path`.
