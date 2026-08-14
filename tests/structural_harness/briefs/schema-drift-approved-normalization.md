# Queue this workflow despite the schema drift

The compiled payload carries an input the live runtime schema does not declare.
Before queueing, surface every required change as a typed proposal. Do NOT
apply any change without explicit approval bound to that exact proposal; when
approved, apply exactly the proposed operations and record them as evidence.
