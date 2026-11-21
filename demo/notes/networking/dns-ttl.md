# DNS TTL

TTL is how long a resolver may cache a record before asking again.

## Picking a value

- 300 seconds for records that may move, such as a service behind a failover.
- 3600 seconds or more for records that never change, such as MX.

## Before a migration

Lower the TTL to 60 seconds one full old-TTL period before the change. Otherwise resolvers keep the old address for up to the old TTL.
