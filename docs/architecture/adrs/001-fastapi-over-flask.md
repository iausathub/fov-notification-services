# ADR-001: FastAPI over Flask

## Status
Accepted

## Context
Building a new notification service for satellite operators and observers 
for different aspects of FOV interference notifications.

## Decision
Use FastAPI instead of Flask (which SatChecker uses).

## Rationale
- Native async for notification-heavy workload
- Built-in WebSocket support for status page
- Starting fresh, no migration cost
- Computationally heavy tasks remain in SatChecker.
- Initial iteration needs to be delivered quickly - this gets the inital framework sooner.

## Consequences
- Need to learn anything additional for FastAPI patterns
- Can't directly share Flask blueprints with SatChecker