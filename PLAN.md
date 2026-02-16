# Documentation Improvement Plan

## Project Goal

Improve the agent system documentation to make development easier for both human and AI developers. Focus on creating comprehensive feature documentation that provides quick, contextual access to relevant information when working on specific features or components.

## Current State Analysis

### Existing Documentation

**Strong points:**
- Comprehensive CLAUDE.md with architecture overview, quick reference, and detailed module creation guide
- Individual module documentation in `agent/docs/modules/` (17+ modules documented)
- ADDING_MODULES.md provides step-by-step guide for creating new modules
- portal.md documents the web portal architecture
- README.md provides good quick start guide

**Weaknesses identified:**
1. **No core service documentation** - Agent loop, tool registry, LLM router are only briefly mentioned in CLAUDE.md
2. **No communication layer docs** - Discord/Telegram/Slack bot implementations undocumented
3. **Inconsistent module docs** - Some modules (project_planner, claude_code) have detailed workflow docs, others (research, file_manager) are minimal
4. **No feature-specific guides** - No docs on implementing cross-cutting features like adding new LLM providers, adding new platforms, implementing new DB tables
5. **No troubleshooting guide** - "Known Gotchas" section exists but scattered throughout CLAUDE.md
6. **No API reference** - No centralized docs for shared schemas, database models, or internal APIs
7. **Missing diagrams** - Only ASCII art architecture diagrams
8. **No testing documentation** - No guidance on testing modules or core services
9. **No deployment documentation** - Production deployment scenarios not covered
10. **Context access difficulty** - When working on a feature, agents need to read multiple files to gather context

## Design Principles

### Documentation Structure Philosophy

1. **Hierarchical organization**: Top-level overview → component-specific → feature-specific
2. **Progressive disclosure**: Quick reference at top, details below
3. **Agent-friendly formatting**: Clear section headers, tables, code examples with context
4. **Cross-referencing**: Link related docs explicitly
5. **Location awareness**: Each doc states its scope and related files
6. **Searchability**: Consistent naming conventions, keywords in headers

### Target Audiences

1. **AI agents** (primary): Working on specific features, need fast context access
2. **Human developers** (secondary): Understanding system architecture, adding features
3. **New contributors**: Getting started, understanding conventions

## Proposed Documentation Structure

```
agent/
├── CLAUDE.md                          # [ENHANCED] Main entry point + quick reference
├── README.md                          # [KEEP] User-facing quick start
├── docs/
│   ├── INDEX.md                       # [NEW] Complete documentation index with descriptions
│   │
│   ├── architecture/                  # [NEW] System architecture deep dives
│   │   ├── overview.md               # High-level system design
│   │   ├── data-flow.md              # Request/response lifecycle diagrams
│   │   ├── database-schema.md        # Complete schema with relationships
│   │   ├── module-system.md          # Module discovery, routing, execution
│   │   └── deployment.md             # Docker compose, networking, volumes
│   │
│   ├── core/                          # [NEW] Core service documentation
│   │   ├── overview.md               # Core service architecture
│   │   ├── agent-loop.md             # Agent loop internals, iteration cycle
│   │   ├── tool-registry.md          # Discovery, caching, execution routing
│   │   ├── llm-router.md             # Provider abstraction, fallback chain
│   │   ├── context-builder.md        # Memory retrieval, summarization, prompt building
│   │   └── memory-system.md          # Summarization, semantic recall, embeddings
│   │
│   ├── comms/                         # [NEW] Communication layer docs
│   │   ├── overview.md               # Bot architecture, common patterns
│   │   ├── discord-bot.md            # Discord.py implementation details
│   │   ├── telegram-bot.md           # python-telegram-bot implementation
│   │   ├── slack-bot.md              # slack-bolt implementation
│   │   └── file-pipeline.md          # Attachment handling across platforms
│   │
│   ├── modules/                       # [ENHANCED] Module documentation
│   │   ├── overview.md               # [ENHANCED] Add discovery flow diagrams
│   │   ├── ADDING_MODULES.md         # [MOVED] Move from parent dir
│   │   ├── research.md               # [ENHANCED] Add implementation details
│   │   ├── file_manager.md           # [ENHANCED] Add MinIO setup, error handling
│   │   ├── code_executor.md          # [ENHANCED] Add security model, sandboxing
│   │   ├── knowledge.md              # [ENHANCED] Add embedding flow, vector search
│   │   ├── atlassian.md              # [KEEP] Already detailed
│   │   ├── claude_code.md            # [ENHANCED] Add Docker-in-Docker details
│   │   ├── deployer.md               # [ENHANCED] Add project type detection
│   │   ├── scheduler.md              # [ENHANCED] Add workflow chaining examples
│   │   ├── garmin.md                 # [ENHANCED] Add OAuth flow
│   │   ├── renpho_biometrics.md      # [ENHANCED] Add API integration details
│   │   ├── location.md               # [ENHANCED] Add OwnTracks protocol
│   │   ├── git_platform.md           # [KEEP] Already detailed
│   │   ├── myfitnesspal.md           # [ENHANCED] Add authentication
│   │   ├── project_planner.md        # [KEEP] Already excellent
│   │   └── injective.md              # [ENHANCE] When implemented
│   │
│   ├── features/                      # [NEW] Feature implementation guides
│   │   ├── adding-llm-provider.md    # Step-by-step guide with code examples
│   │   ├── adding-platform-bot.md    # New platform integration guide
│   │   ├── adding-database-table.md  # Model creation, migration, relationships
│   │   ├── adding-persona-features.md # Extending persona system
│   │   ├── implementing-workflows.md # Multi-module workflow patterns
│   │   ├── file-generation.md        # Creating and returning files from tools
│   │   ├── background-jobs.md        # Scheduler integration patterns
│   │   ├── authentication.md         # External API auth patterns
│   │   └── testing-modules.md        # Module testing strategies
│   │
│   ├── api-reference/                 # [NEW] API and schema reference
│   │   ├── shared-schemas.md         # ToolCall, ToolResult, IncomingMessage, etc.
│   │   ├── database-models.md        # All ORM models with relationships
│   │   ├── core-endpoints.md         # Core service HTTP/WS endpoints
│   │   ├── module-contract.md        # /manifest, /execute, /health specs
│   │   └── shared-utilities.md       # Config helpers, database utilities
│   │
│   ├── development/                   # [NEW] Development workflows
│   │   ├── getting-started.md        # Local setup, first module
│   │   ├── testing.md                # Testing strategies, fixtures
│   │   ├── debugging.md              # Log analysis, common issues
│   │   ├── makefile-reference.md     # All make targets explained
│   │   └── code-standards.md         # Python conventions, structlog usage
│   │
│   ├── deployment/                    # [NEW] Production deployment
│   │   ├── production-setup.md       # Production docker-compose, env vars
│   │   ├── secrets-management.md     # API keys, credentials
│   │   ├── monitoring.md             # Logging, metrics, alerting
│   │   ├── backup-restore.md         # Database and file backups
│   │   └── scaling.md                # Horizontal scaling considerations
│   │
│   ├── troubleshooting/               # [NEW] Problem diagnosis
│   │   ├── common-issues.md          # FAQ and solutions
│   │   ├── module-issues.md          # Module-specific troubleshooting
│   │   ├── platform-issues.md        # Bot connection problems
│   │   ├── database-issues.md        # Migration, query problems
│   │   └── performance.md            # Performance debugging
│   │
│   └── portal.md                      # [MOVED] Move to docs/ for consistency
```

## Implementation Phases

### Phase 1: Documentation Infrastructure & Index (Foundation)

**Goal:** Create the documentation structure and navigation system

**Tasks:**

1. **Create documentation index (`docs/INDEX.md`)**
   - Description: Comprehensive index of all documentation with descriptions and use cases
   - Acceptance Criteria:
     - Lists all documentation files with one-line descriptions
     - Organized by category matching directory structure
     - Includes "When to read this" guidance for each doc
     - Links work correctly from root directory

2. **Enhance CLAUDE.md as main entry point**
   - Description: Update CLAUDE.md to focus on quick reference and point to detailed docs
   - Acceptance Criteria:
     - Quick Reference section remains intact
     - Architecture overview points to `docs/architecture/` for details
     - Module section links to individual module docs
     - Add "For detailed information, see..." sections throughout
     - Add link to `docs/INDEX.md` at top

3. **Create documentation structure**
   - Description: Create all directory structure and placeholder files
   - Acceptance Criteria:
     - All directories from proposed structure created
     - Each directory has a README.md explaining its purpose
     - Placeholder `.md` files created with headers and TODO sections

### Phase 2: Core Service Documentation (Critical Context)

**Goal:** Document the core orchestrator components that are frequently modified

**Tasks:**

1. **Document agent loop (`docs/core/agent-loop.md`)**
   - Description: Deep dive into the agent reasoning cycle
   - Acceptance Criteria:
     - Explain each of the 9 steps in detail
     - Code references to `agent/core/orchestrator/agent_loop.py` with line numbers
     - Diagram of iteration flow
     - Examples of tool use cycles
     - User resolution and permission checking details
     - Budget tracking implementation

2. **Document tool registry (`docs/core/tool-registry.md`)**
   - Description: Module discovery and tool routing internals
   - Acceptance Criteria:
     - Discovery process on startup
     - Redis caching strategy
     - Permission filtering logic
     - Tool name routing (splitting on `.`)
     - Manifest validation
     - Error handling for unreachable modules
     - Code references to `agent/core/orchestrator/tool_registry.py`

3. **Document LLM router (`docs/core/llm-router.md`)**
   - Description: Provider abstraction and fallback mechanism
   - Acceptance Criteria:
     - Provider registration system
     - Fallback chain logic
     - Request/response normalization
     - Token counting per provider
     - Error handling and retry logic
     - Adding new providers guide (cross-reference to features/)
     - Code references to `agent/core/llm_router/router.py`

4. **Document context builder (`docs/core/context-builder.md`)**
   - Description: How context is assembled for LLM calls
   - Acceptance Criteria:
     - System prompt construction
     - Persona integration
     - Memory retrieval (semantic + summary)
     - Conversation history windowing
     - File attachment enrichment
     - Token budget considerations
     - Active project injection

5. **Document memory system (`docs/core/memory-system.md`)**
   - Description: Summarization and semantic recall
   - Acceptance Criteria:
     - When conversations are summarized
     - Embedding generation via `/embed` endpoint
     - Vector similarity search with pgvector
     - Memory creation from summaries
     - Recall scoring and ranking
     - Code references to `agent/core/memory/`

6. **Create core overview (`docs/core/overview.md`)**
   - Description: High-level core service architecture
   - Acceptance Criteria:
     - Component diagram
     - Request lifecycle
     - Dependencies between components
     - Key files and their purposes
     - Links to detailed component docs

### Phase 3: Communication Layer Documentation

**Goal:** Document bot implementations and platform integration patterns

**Tasks:**

1. **Document Discord bot (`docs/comms/discord-bot.md`)**
   - Description: Discord.py implementation details
   - Acceptance Criteria:
     - Event handlers (on_message, on_ready)
     - Attachment download and upload
     - Message formatting (embed vs plain text)
     - Thread handling
     - Rate limiting considerations
     - Code references to `agent/comms/discord_bot/bot.py`

2. **Document Telegram bot (`docs/comms/telegram-bot.md`)**
   - Description: python-telegram-bot implementation
   - Acceptance Criteria:
     - Update handlers
     - File handling (documents, photos, voice)
     - Keyboard markup formatting
     - Group vs private chat handling
     - Code references to `agent/comms/telegram_bot/bot.py`

3. **Document Slack bot (`docs/comms/slack-bot.md`)**
   - Description: slack-bolt implementation
   - Acceptance Criteria:
     - Socket mode setup
     - Event subscriptions
     - File upload/download via API
     - Thread handling
     - App mentions vs DMs
     - Code references to `agent/comms/slack_bot/bot.py`

4. **Document file pipeline (`docs/comms/file-pipeline.md`)**
   - Description: End-to-end file handling across platforms
   - Acceptance Criteria:
     - User upload flow (bot → MinIO → core → DB)
     - Agent generation flow (module → MinIO → DB → bot)
     - File enrichment in user messages
     - MinIO bucket policy setup
     - Public URL generation
     - Security considerations

5. **Create comms overview (`docs/comms/overview.md`)**
   - Description: Common bot architecture patterns
   - Acceptance Criteria:
     - IncomingMessage normalization
     - AgentResponse formatting
     - Error handling patterns
     - Restart behavior on missing tokens
     - Adding new platform guide (cross-reference to features/)

### Phase 4: Enhanced Module Documentation

**Goal:** Expand all module docs to include implementation details and troubleshooting

**Tasks:**

1. **Enhance research module docs**
   - Description: Add implementation details to `docs/modules/research.md`
   - Acceptance Criteria:
     - DuckDuckGo API usage and rate limits
     - BeautifulSoup parsing strategy
     - Summarization flow (calls core /message)
     - Error handling for network failures
     - Testing approach

2. **Enhance file_manager module docs**
   - Description: Add MinIO details to `docs/modules/file_manager.md`
   - Acceptance Criteria:
     - MinIO client initialization
     - Bucket creation and policy setting
     - MIME type detection logic
     - Filename sanitization rules
     - File size limits
     - Integration with code_executor

3. **Enhance code_executor module docs**
   - Description: Add security model to `docs/modules/code_executor.md`
   - Acceptance Criteria:
     - Subprocess sandboxing approach
     - Shell command blocklist
     - Installed packages (numpy, pandas, matplotlib, etc.)
     - File detection and auto-upload
     - Timeout handling
     - Security considerations

4. **Enhance knowledge module docs**
   - Description: Add embedding flow to `docs/modules/knowledge.md`
   - Acceptance Criteria:
     - Memory creation workflow
     - Embedding generation via core `/embed`
     - Vector similarity search SQL
     - Memory management (forgetting)
     - User isolation

5. **Enhance claude_code module docs**
   - Description: Add Docker-in-Docker details to `docs/modules/claude_code.md`
   - Acceptance Criteria:
     - Docker socket mounting
     - Container lifecycle management
     - Workspace persistence
     - Task state machine
     - Plan/execute mode flow
     - Continuation mechanism
     - Git integration details

6. **Enhance deployer module docs**
   - Description: Add project detection to `docs/modules/deployer.md`
   - Acceptance Criteria:
     - Project type detection logic
     - Docker build process
     - Port allocation
     - Environment variable injection
     - Log streaming
     - Teardown cleanup

7. **Enhance scheduler module docs**
   - Description: Add workflow chaining examples to `docs/modules/scheduler.md`
   - Acceptance Criteria:
     - Job types (poll_module, poll_url, delay)
     - Resume conversation mechanism
     - Interval and max attempts
     - Success/failure callbacks
     - Example workflows (claude_code → deployer)

8. **Enhance location module docs**
   - Description: Add OwnTracks protocol to `docs/modules/location.md`
   - Acceptance Criteria:
     - OwnTracks HTTP endpoint
     - Region sync to device
     - Geofence trigger logic
     - Credential generation
     - Named places

9. **Enhance remaining modules**
   - Description: Add authentication and API details to garmin, renpho, myfitnesspal
   - Acceptance Criteria:
     - OAuth/API key flows
     - Request/response examples
     - Rate limiting
     - Error handling

10. **Move and enhance ADDING_MODULES.md**
    - Description: Move to `docs/modules/` and add more examples
    - Acceptance Criteria:
      - Update all references in other docs
      - Add troubleshooting section
      - Add more complete working examples
      - Add testing section

11. **Enhance modules overview**
    - Description: Add discovery flow diagrams to `docs/modules/overview.md`
    - Acceptance Criteria:
      - Sequence diagram of discovery
      - Execution flow diagram
      - Permission filtering visualization
      - Cross-module workflow examples

### Phase 5: Feature Implementation Guides

**Goal:** Create step-by-step guides for common development tasks

**Tasks:**

1. **Create adding-llm-provider guide (`docs/features/adding-llm-provider.md`)**
   - Description: Complete guide to adding a new LLM provider
   - Acceptance Criteria:
     - Create provider class in `llm_router/providers/`
     - Implement BaseLLMProvider interface
     - Normalize responses
     - Add to router registration
     - Update config settings
     - Testing the integration
     - Full working example

2. **Create adding-platform-bot guide (`docs/features/adding-platform-bot.md`)**
   - Description: Guide to integrating a new chat platform
   - Acceptance Criteria:
     - Bot structure and dependencies
     - Message normalization
     - File handling
     - Response formatting
     - Docker service setup
     - Testing with core

3. **Create adding-database-table guide (`docs/features/adding-database-table.md`)**
   - Description: Step-by-step database schema changes
   - Acceptance Criteria:
     - Create model in shared/models/
     - Relationship patterns (FK, back_populates)
     - Alembic migration creation
     - Migration testing
     - Rollback procedures
     - Example with multiple tables

4. **Create implementing-workflows guide (`docs/features/implementing-workflows.md`)**
   - Description: Multi-module workflow patterns
   - Acceptance Criteria:
     - Scheduler-based workflows
     - Error handling between steps
     - State management
     - Examples: claude_code → deployer, research → knowledge
     - Resume conversation pattern

5. **Create file-generation guide (`docs/features/file-generation.md`)**
   - Description: How modules create and return files
   - Acceptance Criteria:
     - Upload to MinIO
     - Create FileRecord
     - Return in ToolResult
     - Orchestrator extraction
     - Bot download and display

6. **Create background-jobs guide (`docs/features/background-jobs.md`)**
   - Description: Scheduler integration patterns
   - Acceptance Criteria:
     - Job types and use cases
     - Creating polling jobs
     - Resume conversation mechanism
     - Timeout and retry handling
     - Notification patterns

7. **Create authentication guide (`docs/features/authentication.md`)**
   - Description: External API authentication patterns
   - Acceptance Criteria:
     - OAuth 2.0 flow
     - API key management
     - Token refresh
     - Per-user credentials storage
     - Example implementations (Garmin, Atlassian)

8. **Create testing-modules guide (`docs/features/testing-modules.md`)**
   - Description: Module testing strategies
   - Acceptance Criteria:
     - Unit testing tool methods
     - Integration testing /execute endpoint
     - Mocking dependencies
     - Database fixtures
     - Example test suite

### Phase 6: API Reference Documentation

**Goal:** Create comprehensive reference for schemas, models, and APIs

**Tasks:**

1. **Create shared-schemas reference (`docs/api-reference/shared-schemas.md`)**
   - Description: Document all Pydantic schemas in shared/schemas/
   - Acceptance Criteria:
     - ToolCall, ToolResult, ModuleManifest
     - IncomingMessage, AgentResponse
     - ToolDefinition, ToolParameter
     - Field descriptions and types
     - Validation rules
     - Usage examples

2. **Create database-models reference (`docs/api-reference/database-models.md`)**
   - Description: Complete ORM model reference
   - Acceptance Criteria:
     - All models with field descriptions
     - Relationship diagrams
     - Unique constraints and indexes
     - Cascade behaviors
     - Query examples for common operations

3. **Create core-endpoints reference (`docs/api-reference/core-endpoints.md`)**
   - Description: Core service HTTP and WebSocket endpoints
   - Acceptance Criteria:
     - POST /message
     - POST /embed
     - POST /continue
     - GET /health
     - Request/response schemas
     - Error codes

4. **Create module-contract reference (`docs/api-reference/module-contract.md`)**
   - Description: Specification for module endpoints
   - Acceptance Criteria:
     - GET /manifest spec
     - POST /execute spec
     - GET /health spec
     - Timeout expectations
     - Error response format

5. **Create shared-utilities reference (`docs/api-reference/shared-utilities.md`)**
   - Description: Document shared package utilities
   - Acceptance Criteria:
     - get_settings() and config
     - get_session_factory() usage
     - get_redis() usage
     - parse_list() helper
     - upload_attachment() from file_utils
     - Logging with structlog

### Phase 7: Architecture Documentation

**Goal:** Create comprehensive architecture documentation

**Tasks:**

1. **Create architecture overview (`docs/architecture/overview.md`)**
   - Description: High-level system design
   - Acceptance Criteria:
     - Component diagram
     - Service dependencies
     - Network topology (agent-net)
     - Technology stack
     - Design decisions and rationale

2. **Create data-flow documentation (`docs/architecture/data-flow.md`)**
   - Description: Request/response lifecycle with diagrams
   - Acceptance Criteria:
     - User message → agent response flow
     - Tool execution flow
     - File upload flow
     - Background job flow
     - Memory creation and recall flow
     - Sequence diagrams

3. **Create database-schema documentation (`docs/architecture/database-schema.md`)**
   - Description: Complete schema with relationships
   - Acceptance Criteria:
     - ERD diagram (can be ASCII or mermaid)
     - Table-by-table descriptions
     - Relationship explanations
     - Index strategy
     - Migration history approach

4. **Create module-system documentation (`docs/architecture/module-system.md`)**
   - Description: Module architecture design
   - Acceptance Criteria:
     - Why microservices
     - Discovery mechanism
     - Routing strategy
     - Isolation benefits
     - Shared package approach
     - Performance considerations

5. **Create deployment documentation (`docs/architecture/deployment.md`)**
   - Description: Docker Compose infrastructure
   - Acceptance Criteria:
     - Service definitions
     - Network configuration
     - Volume mounts
     - Environment variables
     - Startup order and dependencies
     - Health checks

### Phase 8: Development and Deployment Documentation

**Goal:** Support developers and operators

**Tasks:**

1. **Create getting-started guide (`docs/development/getting-started.md`)**
   - Description: Onboarding for new developers
   - Acceptance Criteria:
     - Prerequisites
     - First-time setup
     - Creating first module (tutorial)
     - Development workflow
     - Common commands

2. **Create testing guide (`docs/development/testing.md`)**
   - Description: Testing strategies and tools
   - Acceptance Criteria:
     - Unit testing approach
     - Integration testing
     - Database fixtures
     - Mocking external APIs
     - Running tests in Docker

3. **Create debugging guide (`docs/development/debugging.md`)**
   - Description: Problem diagnosis techniques
   - Acceptance Criteria:
     - Log analysis with structlog
     - Using make shell
     - Database queries
     - Redis inspection
     - Network debugging

4. **Create makefile-reference (`docs/development/makefile-reference.md`)**
   - Description: All make targets explained
   - Acceptance Criteria:
     - Every target documented
     - Grouped by category
     - Use cases for each
     - Examples

5. **Create code-standards guide (`docs/development/code-standards.md`)**
   - Description: Python conventions and best practices
   - Acceptance Criteria:
     - Type hints usage
     - Async/await patterns
     - Structlog usage
     - Error handling patterns
     - Naming conventions

6. **Create production-setup guide (`docs/deployment/production-setup.md`)**
   - Description: Production deployment guide
   - Acceptance Criteria:
     - Production docker-compose variations
     - Reverse proxy setup (nginx)
     - SSL/TLS configuration
     - Environment separation
     - Resource limits

7. **Create secrets-management guide (`docs/deployment/secrets-management.md`)**
   - Description: Handling API keys and credentials
   - Acceptance Criteria:
     - Environment variable best practices
     - Secret rotation
     - Per-user credential storage
     - Encryption considerations

8. **Create monitoring guide (`docs/deployment/monitoring.md`)**
   - Description: Observability setup
   - Acceptance Criteria:
     - Log aggregation
     - Metrics collection
     - Alerting strategies
     - Dashboard setup

9. **Create backup-restore guide (`docs/deployment/backup-restore.md`)**
   - Description: Data protection procedures
   - Acceptance Criteria:
     - PostgreSQL backup
     - MinIO backup
     - Restore procedures
     - Disaster recovery

### Phase 9: Troubleshooting Documentation

**Goal:** Help diagnose and fix common issues

**Tasks:**

1. **Create common-issues guide (`docs/troubleshooting/common-issues.md`)**
   - Description: FAQ and solutions
   - Acceptance Criteria:
     - Module discovery failures
     - Permission errors
     - Token budget exceeded
     - Network connectivity issues
     - Each with diagnosis and fix

2. **Create module-issues guide (`docs/troubleshooting/module-issues.md`)**
   - Description: Module-specific troubleshooting
   - Acceptance Criteria:
     - Module not responding
     - Tool execution timeout
     - Database connection failures
     - MinIO access issues

3. **Create platform-issues guide (`docs/troubleshooting/platform-issues.md`)**
   - Description: Bot connection problems
   - Acceptance Criteria:
     - Bot not responding
     - Authentication failures
     - File upload/download issues
     - Rate limiting

4. **Create database-issues guide (`docs/troubleshooting/database-issues.md`)**
   - Description: Database and migration problems
   - Acceptance Criteria:
     - Migration failures
     - Alembic conflicts
     - Connection pool exhaustion
     - Slow queries

5. **Create performance guide (`docs/troubleshooting/performance.md`)**
   - Description: Performance debugging
   - Acceptance Criteria:
     - Slow agent responses
     - High memory usage
     - Database query optimization
     - Redis cache tuning

### Phase 10: Documentation Polish and Cross-Linking

**Goal:** Ensure all documentation is interconnected and complete

**Tasks:**

1. **Add cross-references throughout documentation**
   - Description: Link related docs to each other
   - Acceptance Criteria:
     - Every doc links to related docs
     - CLAUDE.md links to all detailed docs
     - Module docs link to feature guides
     - Feature guides link to API reference
     - No dead links

2. **Add "Quick Context" sections to all docs**
   - Description: Each doc starts with quick context box
   - Acceptance Criteria:
     - Related files section
     - Related docs section
     - Key concepts section
     - When to read this doc

3. **Create diagrams for complex flows**
   - Description: Add mermaid diagrams where helpful
   - Acceptance Criteria:
     - Agent loop flow diagram
     - Tool execution sequence diagram
     - Memory retrieval flow
     - File pipeline flow
     - Workflow chaining examples

4. **Add code examples throughout**
   - Description: Every guide has working code examples
   - Acceptance Criteria:
     - Copy-paste ready examples
     - Full context provided
     - Comments explaining key points
     - Error handling shown

5. **Update CLAUDE.md with new structure**
   - Description: Revise CLAUDE.md to be a true entry point
   - Acceptance Criteria:
     - Quick reference remains
     - Links to detailed docs for each section
     - "For detailed X, see docs/Y" throughout
     - Architecture ASCII art links to docs/architecture/

6. **Create docs/README.md**
   - Description: Documentation directory overview
   - Acceptance Criteria:
     - Explains directory structure
     - Links to INDEX.md
     - Quick navigation guide
     - Contribution guidelines

## Success Criteria

### For AI Agents Working on Features

1. **Context acquisition < 3 file reads**: Agent can find relevant documentation in ≤3 file reads for any common task
2. **Self-contained docs**: Each document provides enough context to understand its scope without reading others
3. **Code references**: Documentation includes file paths and line numbers for code examples
4. **Examples for every pattern**: Common patterns have complete working examples

### For Human Developers

1. **Onboarding time**: New developer can create a working module in <2 hours with docs alone
2. **Troubleshooting success**: Common issues can be diagnosed using troubleshooting docs
3. **Architecture understanding**: System design is clear from architecture docs
4. **Navigation**: Can find any information in <2 clicks from CLAUDE.md or INDEX.md

### For Documentation Maintenance

1. **Update locations are obvious**: When code changes, it's clear which docs need updates
2. **No duplication**: Each concept documented in one place, referenced elsewhere
3. **Versioning**: Documentation changes tracked in git alongside code
4. **Completeness**: Every module, feature, and component has documentation

## Implementation Notes

### Tooling

- **Diagrams**: Use mermaid.js syntax (supported by GitHub, many renderers)
- **Code blocks**: Always specify language for syntax highlighting
- **Tables**: Use markdown tables for structured data
- **Links**: Use relative paths from repository root

### Writing Style

- **Concise**: Short paragraphs, bullet points
- **Imperative**: "Create file X" not "You should create file X"
- **Specific**: Include actual code, not pseudocode
- **Progressive**: Overview first, details after
- **Complete**: Include error cases, edge cases

### Agent-Friendly Patterns

- **Section headers are questions**: "How does discovery work?" not "Discovery"
- **Tables for comparison**: When multiple options exist
- **Code blocks with full context**: Include imports, not just functions
- **File location in every doc**: State which files the doc describes
- **Prerequisites explicit**: State what to read first

### Maintenance Plan

After initial creation:

1. **Docs review in PRs**: Any code change that affects behavior requires doc update
2. **Quarterly review**: Review INDEX.md quarterly to ensure completeness
3. **Link checking**: Automated link checker in CI
4. **Example testing**: Code examples should be testable (extract and run)

## Migration Strategy

### Phase 1 Implementation

Start with most valuable docs for agents:

1. Create INDEX.md (navigation hub)
2. Core service docs (most frequently needed context)
3. Enhanced module docs (agents work on modules often)
4. Feature guides for common tasks

### Gradual Enhancement

- Existing docs remain valid, linked from new structure
- New docs added incrementally by phase
- CLAUDE.md remains comprehensive until Phase 10
- No breaking changes to existing documentation

### Validation

After each phase:

1. Test with AI agent: Can it find information quickly?
2. Human review: Is it clear and accurate?
3. Link check: All cross-references work
4. Example verification: Code examples are correct

## File Inventory

### Files to Create (Estimated 60+ new files)

**Phase 1**: 3 files (INDEX.md, directory READMEs)
**Phase 2**: 6 files (core service docs)
**Phase 3**: 5 files (comms layer docs)
**Phase 4**: 11 files (enhanced module docs)
**Phase 5**: 8 files (feature guides)
**Phase 6**: 5 files (API reference)
**Phase 7**: 5 files (architecture)
**Phase 8**: 9 files (development & deployment)
**Phase 9**: 5 files (troubleshooting)
**Phase 10**: Enhancements to existing files

### Files to Enhance

- CLAUDE.md (add links to detailed docs)
- All existing module docs (add implementation details)
- README.md (minor updates for consistency)

### Files to Move

- agent/docs/ADDING_MODULES.md → agent/docs/modules/ADDING_MODULES.md
- agent/docs/portal.md → agent/docs/modules/portal.md (treat portal as a module)

## Estimated Effort

### By Phase (Story Points using Fibonacci)

- **Phase 1**: 3 points (infrastructure)
- **Phase 2**: 13 points (core docs, most complex)
- **Phase 3**: 8 points (comms layer)
- **Phase 4**: 21 points (11 module enhancements)
- **Phase 5**: 13 points (feature guides)
- **Phase 6**: 8 points (API reference)
- **Phase 7**: 8 points (architecture)
- **Phase 8**: 13 points (dev & deployment)
- **Phase 9**: 8 points (troubleshooting)
- **Phase 10**: 5 points (polish)

**Total**: ~100 story points

### Priority Order for Incremental Value

If implementing incrementally, prioritize:

1. **Phase 1** (foundation)
2. **Phase 2** (core docs - highest value for agents)
3. **Phase 4** (module enhancements)
4. **Phase 5** (feature guides)
5. **Phase 3** (comms layer)
6. **Phase 6** (API reference)
7. **Phases 7-9** (architecture, dev, troubleshooting)
8. **Phase 10** (polish)

## Conclusion

This plan transforms the documentation from a collection of scattered references into a comprehensive, navigable knowledge base optimized for both AI agents and human developers. The hierarchical structure, progressive disclosure, and extensive cross-linking will dramatically reduce context acquisition time and improve development velocity.

The phased approach allows for incremental implementation while maintaining the value of existing documentation. Each phase delivers standalone value, and the system remains functional throughout the migration.
