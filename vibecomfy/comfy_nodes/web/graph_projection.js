// Compatibility facade. All structural/layout projection semantics live in
// projection_registry_v1.js.
export {
  assertRootScopeLayoutGraph,
  buildLayoutGraphProjection,
  buildStructuralGraphProjection,
  findUnsupportedNestedLayoutScopes,
  layoutGraphProjectionJson,
  structuralGraphProjectionJson,
} from "./projection_registry_v1.js";
