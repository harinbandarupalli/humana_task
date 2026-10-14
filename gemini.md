# Project Operating Guidelines (gemini.md)

## Development Workflow Protocol
To maintain high architectural standards, consistency, and alignment, follow the strict 3-step cycle for all features and changes:

1. **PLAN**:
   - Break down business logic, edge cases, data flow, and failure states.
   - Design data structures, schemas, and API interfaces.
   - Identify dependencies, migrations, and idempotency mechanisms.

2. **REVIEW**:
   - Present the comprehensive plan and architecture diagrams (e.g., Mermaid entity-relationship and state flow diagrams).
   - Detail table structures, column definitions, data types, and indexing strategies.
   - Solicit and discuss feedback, edge cases, and alternatives with the user.

3. **IMPLEMENT (Only After Approval)**:
   - Do NOT write or execute production migrations/code until explicit approval is received on the plan and design.
   - Implement clean, tested, documented, and production-ready code.
