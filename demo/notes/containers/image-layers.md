# Docker image layers

Each instruction in a Dockerfile creates a layer. A layer is rebuilt when its instruction or anything before it changes.

## Order for cache hits

Put what changes least first:

1. Base image
2. System packages
3. Dependency manifest (`requirements.txt`, `package.json`) and the install step
4. Application code

Copying the code before installing dependencies reinstalls everything on every code change.

## Smaller images

- Use a multi-stage build: compile in one stage, copy only the result into the final one.
- Remove package manager caches in the same `RUN` that created them; a later `RUN rm` does not shrink earlier layers.
