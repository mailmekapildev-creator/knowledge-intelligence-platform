# ADR-001: Multi-Tenancy Isolation Model

**Status:** Accepted

## Context
The platform serves multiple tenants sharing infrastructure. We need an isolation model that
balances security guarantees against cost and operational complexity.

## Options considered
1. **Silo** — dedicated DB + vector index per tenant.
2. **Pool** — shared tables/index, filtered by `tenant_id` column only.
3. **Hybrid (namespace-per-tenant on shared infra)** — shared Postgres cluster with row-level
   security, shared vector engine with per-tenant logical namespaces.

## Decision
Hybrid model (3), with a documented promotion path to Silo (1) for large or regulated
tenants who require it contractually.

## Consequences
- Cost stays close to the Pool model for the common case.
- Isolation is enforced at two layers (RLS + vector namespace), not one, reducing blast
  radius of an application-layer bug.
- Large tenants can be moved to dedicated infra without an application rewrite — the
  namespace abstraction is the same shape as a silo, just backed by shared infra.
- Trade-off accepted: slightly more complex query layer (must always resolve and pass
  tenant namespace) versus the Pool model's simplicity.
