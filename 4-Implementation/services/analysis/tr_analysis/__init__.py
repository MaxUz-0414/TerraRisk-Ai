"""TerraRisk `analysis` service: the orchestrator. One request in, the whole analysis out.

It owns no data. It calls satellite -> risk -> advisory (+ geocode in parallel) and says honestly what it could not get.
Design note (see ARCHITECTURE.md, "granularity"): the web app could call these services itself, but then every client would
have to know the order, the failure rules and the data hand-offs. Putting that in one place costs one extra network hop and
gives us one place to change the workflow.
"""
