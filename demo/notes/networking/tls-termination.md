# TLS termination

Where the encrypted part of a connection ends when a load balancer sits in front of the servers.

## Three setups

| Setup | TLS ends at | Certificate lives on |
|---|---|---|
| Termination | The load balancer | The load balancer |
| Passthrough | The backend server | The backend server |
| Re-encryption | The load balancer, then a second TLS connection to the backend | Both |

## Termination

The client talks HTTPS to the load balancer. The load balancer decrypts and forwards plain HTTP to the backend over the private network.

- Backends need no certificate.
- The backend learns the original scheme from the `X-Forwarded-Proto` header.
- Acceptable when the private network is trusted and only the load balancer can reach the backends.

## When to avoid it

If a rule says traffic must be encrypted everywhere in transit, use passthrough or re-encryption.
