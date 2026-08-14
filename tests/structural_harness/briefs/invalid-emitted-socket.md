# Emit the graph

Emit the attached workflow to the UI graph format. One link references a
source socket that no emitted node socket can match. Handle it honestly: the
whole emit must be refused with full endpoint/socket evidence — never drop the
edge silently.
