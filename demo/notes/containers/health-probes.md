# Kubernetes health probes

## Liveness

Answers "should this container be restarted?". A failing liveness probe kills the container.

Do not check dependencies here. If the database is down, restarting every pod makes things worse.

## Readiness

Answers "should this pod receive traffic?". A failing readiness probe removes the pod from the Service endpoints without restarting it.

## Startup

Protects slow-starting containers: liveness and readiness do not run until the startup probe succeeds.
