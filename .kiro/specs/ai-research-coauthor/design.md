# Design Document: AI Research Co-Author

## Overview

The AI Research Co-Author is a multi-agent system that generates citation-grounded research-paper-style drafts through specialized AI agents orchestrated by a custom Manager/Controller Process (MCP). The system architecture emphasizes explainability, traceability, and separation of concerns.

The system follows a pipeline architecture where three specialized agents (Reviewer, Methodology, Critic) execute sequentially, each building upon the previous agent's output. All intermediate results and reasoning are persisted to PostgreSQL to provide complete audit trails and explainability.

**Key Design Principles:**
- Single Responsibility: Each agent has one clear purpose
- Explainability: All outputs are traceable to their sources
- Citation Grounding: All claims are backed by references
- Custom Orchestration: MCP controls flow without generating content
- Persistence: Complete audit trail stored in PostgreSQL

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Manager/Controller Process (MCP)             │  │
│  │                                                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │   Reviewer   │→ │ Methodology  │→ │    Critic    │  │  │
│  │  │    Agent     │  │    Agent     │  │    Agent     │  │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │  │
│  │         │                  │                  │           │  │
│  │         └──────────────────┴──────────────────┘           │  │
│  │                            │                               │  │
│  │                    ┌───────▼────────┐                     │  │
│  │                    │ Draft Assembler│                     │  │
│  │                    └───────┬────────┘                     │  │
│  └────────────────────────────┼──────────────────────────────┘  │
│                                │                                 │
│  ┌─────────────────────────────▼──────────────────────────────┐ │
│  │              LangChain Components (per agent)               │ │
│  │  • Prompt Templates  • RAG Pipeline  • Output Parsers      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└───────────────────────────┬───────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  PostgreSQL  │    │   Amazon S3  │    │  LLM APIs    │
│              │    │              │    │              │
│ • Drafts     │    │ • PDF Files  │    │ • GPT-4      │
│ • Audit Trail│    │ • Documents  │    │ • Claude     │
│ • Citations  │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Data Flow

1. **Request Initiation**: User submits research topic via FastAPI endpoint
2. **MCP Orchestration**: MCP creates execution plan and initializes audit trail
3. **Reviewer Agent**: 
   - Retrieves relevant literature using RAG
   - Generates literature summary with citations
   - Stores output in PostgreSQL
4. **Methodology Agent**:
   - Receives Reviewer output as context
   - Proposes research methodology grounded in prior work
   - Stores output in PostgreSQL
5. **Critic Agent**:
   - Receives combined context from previous agents
   - Identifies weaknesses, assumptions, and limitations
   - Stores output in PostgreSQL
6. **Draft Assembly**: MCP aggregates agent outputs into structured Research_Draft
7. **Response**: System returns draft ID and complete draft to user

## Components and Interfaces

### 1. FastAPI Backend

**Responsibility**: Expose RESTful API endpoints for draft generation and retrieval

**Key Endpoints**:
- `POST /api/v1/drafts` - Create new draft generation request
- `GET /api/v1/drafts/{draft_id}` - Retrieve completed draft
- `GET /api/v1/drafts/{draft_id}/status` - Check draft generation status
- `GET /api/v1/drafts/{draft_id}/audit` - Retrieve audit trail for explainability
- `POST /api/v1/documents` - Upload PDF documents for reference

**Request/Response Models**:
- DraftRequest: Contains research_topic (string), optional seed_papers (list of S3 keys/URLs), and optional user_preferences
- DraftResponse: Contains draft_id (UUID), status (pending/processing/completed/failed), and created_at timestamp
- CompletedDraft: Contains draft_id, sections (map of section names to content), citations list, and metadata
- AuditTrail: Contains draft_id, agent_outputs list, and execution_timeline

**Error Handling**:
- Input validation using Pydantic models
- HTTP status codes: 200 (success), 400 (bad request), 404 (not found), 500 (server error)
- Structured error responses with error codes and messages

### 2. Manager/Controller Process (MCP)

**Responsibility**: Orchestrate agent execution order, context passing, and draft assembly

**Core Functions**:
- `orchestrate_draft_generation(request: DraftRequest) -> str`: Main orchestration logic
- `execute_agent(agent: Agent, context: Dict) -> AgentOutput`: Execute single agent
- `pass_context(from_agent: str, to_agent: str, data: Dict) -> Dict`: Context transformation
- `assemble_draft(agent_outputs: List[AgentOutput]) -> CompletedDraft`: Aggregate outputs
- `handle_agent_failure(agent: str, error: Exception) -> None`: Error recovery

**Execution Flow**:
1. Initialize audit trail and create draft record with unique ID
2. Execute Reviewer Agent with context containing research topic and optional seed papers
3. Store reviewer output (summary, citations, gaps) to database
4. Execute Methodology Agent with context containing topic, literature summary, and research gaps
5. Store methodology output (proposal, citations, steps) to database
6. Execute Critic Agent with context containing topic, literature summary, and methodology proposal
7. Store critic output (weaknesses, assumptions, limitations, suggestions) to database
8. Assemble final draft by aggregating all agent outputs into structured sections
9. Store completed draft and return draft ID to user

**State Management**:
- Draft status tracked in PostgreSQL: pending → processing → completed/failed
- Progress updates stored for long-running operations
- Idempotent operations to support retries

### 3. Reviewer Agent

**Responsibility**: Summarize existing literature using RAG and identify research gaps

**LangChain Components**:
- Document Loader: Load and parse PDF documents
- Text Splitter: Chunk documents for embedding
- Vector Store: FAISS or Chroma for similarity search
- Retrieval Chain: Query relevant passages
- Prompt Template: Structure literature summarization task

**Core Logic**:
- Initialize with LLM client and vector store for document retrieval
- Build retrieval chain using LangChain components
- On execution:
  1. Retrieve relevant literature using similarity search (top 10 documents)
  2. Generate literature summary using LLM with retrieved documents as context
  3. Extract citations from relevant documents and link to summary claims
  4. Identify research gaps by analyzing what's missing in current literature
  5. Return structured output with summary, citations, gaps, and reasoning trace

**Output Structure**:
- Literature summary (2-3 paragraphs)
- Key themes and trends
- Research gaps
- Citations for all claims
- Intermediate reasoning for explainability

### 4. Methodology Agent

**Responsibility**: Propose research methodologies grounded in prior work

**LangChain Components**:
- Prompt Template: Structure methodology proposal task
- Output Parser: Extract structured methodology from LLM response
- Few-shot Examples: Guide LLM with example methodologies

**Core Logic**:
- Initialize with LLM client and prompt templates
- Build output parser for structured methodology extraction
- On execution:
  1. Build prompt with context (topic, literature summary, research gaps)
  2. Generate methodology proposal using LLM
  3. Parse LLM output into structured methodology format
  4. Extract citations that justify methodology choices
  5. Return structured output with proposal, citations, and reasoning trace

**Output Structure**:
- Proposed methodology description
- Justification grounded in prior work
- Key steps and procedures
- Expected outcomes
- Citations for methodology choices

### 5. Critic Agent

**Responsibility**: Identify weaknesses, assumptions, and limitations

**LangChain Components**:
- Prompt Template: Structure critical analysis task
- Output Parser: Extract structured critique from LLM response

**Core Logic**:
- Initialize with LLM client and critique prompt templates
- Build output parser for structured critique extraction
- On execution:
  1. Build comprehensive critique prompt with all context (topic, literature, methodology)
  2. Generate critical analysis using LLM
  3. Parse LLM output into structured categories
  4. Categorize issues into weaknesses, assumptions, limitations, and suggestions
  5. Return structured output with all critique categories and reasoning trace

**Output Structure**:
- Identified weaknesses
- Stated and unstated assumptions
- Methodological limitations
- Threats to validity
- Constructive suggestions for improvement

### 6. Draft Assembler

**Responsibility**: Aggregate agent outputs into structured research draft

**Section Assembly Logic**:
- Locate outputs from all three agents (Reviewer, Methodology, Critic)
- Generate Abstract by synthesizing key points from all agent outputs (150-200 words)
- Generate Introduction based on research topic and gaps identified by Reviewer
- Use Reviewer summary directly for Related Work section
- Use Methodology Agent proposal directly for Methodology section
- Format Critic output into Limitations section
- Generate Conclusion by synthesizing proposed approach and next steps
- Aggregate all citations from all agents
- Build metadata including agent attribution for each section

**Section Generation**:
- Abstract: Synthesized from all agent outputs (150-200 words)
- Introduction: Based on research topic and gaps from Reviewer
- Related Work: Direct use of Reviewer summary
- Methodology: Direct use of Methodology Agent proposal
- Limitations: Formatted output from Critic Agent
- Conclusion: Synthesized summary of proposed approach and next steps

## Data Models

### Database Schema (PostgreSQL)

**Drafts Table**:
- draft_id (UUID, primary key)
- research_topic (text, not null)
- status (varchar, not null) - values: pending, processing, completed, failed
- created_at, updated_at, completed_at (timestamps)
- error_message (text, nullable)

**Agent Outputs Table**:
- output_id (UUID, primary key)
- draft_id (UUID, foreign key to drafts)
- agent_name (varchar, not null) - values: reviewer, methodology, critic
- output_data (JSONB, not null) - structured agent output
- reasoning (JSONB, nullable) - intermediate reasoning trace
- created_at (timestamp)

**Citations Table**:
- citation_id (UUID, primary key)
- draft_id (UUID, foreign key to drafts)
- agent_name (varchar, not null)
- source_title, source_authors, source_year, source_url (text fields)
- cited_text (text, not null) - the specific text that was cited
- created_at (timestamp)

**Draft Sections Table**:
- section_id (UUID, primary key)
- draft_id (UUID, foreign key to drafts)
- section_name (varchar, not null) - values: abstract, introduction, related_work, methodology, limitations, conclusion
- content (text, not null)
- source_agent (varchar, nullable) - which agent generated this section
- created_at (timestamp)

**Documents Table**:
- document_id (UUID, primary key)
- s3_key (text, not null) - S3 object key
- filename (text, not null)
- uploaded_at (timestamp)
- file_size_bytes (bigint)

**Execution Events Table**:
- event_id (UUID, primary key)
- draft_id (UUID, foreign key to drafts)
- event_type (varchar, not null) - values: agent_start, agent_complete, agent_error, progress_update
- event_data (JSONB, nullable) - additional event details
- timestamp (timestamp)

### Python Data Models

**Core Models**:
- DraftStatus: Enum with values PENDING, PROCESSING, COMPLETED, FAILED
- Citation: Contains citation_id, source metadata (title, authors, year, URL), and cited_text
- AgentOutput: Contains output_id, agent_name, output_data (dict), optional reasoning (dict), citations list, and timestamp
- DraftSection: Contains section_name, content, and source_agent
- CompletedDraft: Contains draft_id, research_topic, sections (dict mapping section names to DraftSection), citations list, metadata, and timestamps
- ExecutionEvent: Contains event_id, draft_id, event_type, event_data (dict), and timestamp

All models use Pydantic for validation and serialization.

## Error Handling

### LLM API Error Handling

**Retry Strategy**:
- Exponential backoff with delays: 1 second, 2 seconds, 4 seconds
- Maximum 3 retry attempts per LLM call
- Timeout: 60 seconds per request
- Retry on: TimeoutError, RateLimitError
- Fail immediately on: AuthenticationError, InvalidRequestError

### Agent Execution Error Handling

**Failure Modes**:
- Agent execution timeout (5 minutes per agent)
- LLM API failures after retries
- Invalid output format from LLM
- Database connection failures

**Recovery Strategy**:
- Log all errors to PostgreSQL execution_events table
- Update draft status to "failed" with error message
- Return descriptive error to user via API
- No automatic retry at MCP level (user must resubmit)

### Database Error Handling

**Connection Management**:
- Use SQLAlchemy connection pooling
- Automatic reconnection on connection loss
- Transaction rollback on errors
- Proper session cleanup in finally blocks

### Input Validation

**Validation Rules**:
- Research topic: 10-500 characters, non-empty
- Seed papers: Valid S3 keys or URLs
- Draft ID: Valid UUID format

**Validation Implementation**:
- Pydantic models for automatic validation
- Custom validators for business logic
- Clear error messages for validation failures

## Testing Strategy

The AI Research Co-Author system requires comprehensive testing across multiple layers to ensure correctness, reliability, and explainability. Testing will employ both unit tests for specific scenarios and property-based tests for universal correctness properties.

### Testing Approach

**Unit Testing**:
- Test specific examples and edge cases
- Verify integration points between components
- Test error handling and recovery logic
- Mock external dependencies (LLM APIs, databases)

**Property-Based Testing**:
- Verify universal properties across randomized inputs
- Test invariants that should hold for all valid inputs
- Use Hypothesis (Python) for property-based testing
- Minimum 100 iterations per property test

**Integration Testing**:
- Test end-to-end draft generation flow
- Verify database persistence and retrieval
- Test MCP orchestration with real agents
- Use test doubles for LLM APIs to ensure deterministic results

### Test Configuration

- Property tests: 100 iterations minimum
- Test timeout: 30 seconds per test
- Mock LLM responses for deterministic testing
- Separate test database for isolation
- Tag format: `# Feature: ai-research-coauthor, Property {N}: {description}`


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: MCP Content Neutrality

*For any* draft generation request, the MCP's output should only contain aggregated agent outputs without any content generated by the MCP itself.

**Validates: Requirements 1.2**

### Property 2: Agent Context Flow

*For any* agent execution in the pipeline, each agent must receive the complete outputs from all previously executed agents in its context.

**Validates: Requirements 1.3, 9.2, 9.3**

### Property 3: Methodology Citation Grounding

*For any* methodology proposal, the output must contain at least one citation from prior work justifying the proposed approach.

**Validates: Requirements 1.5, 5.2**

### Property 4: Critic Output Completeness

*For any* critic agent execution, the output must contain all four required categories: weaknesses, assumptions, threats to validity, and suggestions.

**Validates: Requirements 1.6, 6.1, 6.2, 6.3, 6.4**

### Property 5: Draft Generation Completeness

*For any* valid research topic submitted, the system must generate a complete draft containing all required sections.

**Validates: Requirements 2.1**

### Property 6: Required Sections Presence

*For any* generated research draft, it must contain exactly these six sections: Abstract, Introduction, Related Work, Methodology, Limitations, and Conclusion.

**Validates: Requirements 2.2, 2.3, 2.4, 2.5, 2.6, 2.7**

### Property 7: Agent Citation Inclusion

*For any* agent output that contains factual claims or proposals, the output must include at least one citation.

**Validates: Requirements 3.1, 4.3, 5.2**

### Property 8: Audit Trail Persistence

*For any* completed draft generation, the database must contain all agent outputs, intermediate reasoning, and draft versions with timestamps.

**Validates: Requirements 3.2, 3.3, 3.4, 7.1, 7.2, 7.3, 7.6**

### Property 9: Audit Trail Retrieval Completeness

*For any* draft ID, retrieving the audit trail must return all agent outputs, execution events, and reasoning data associated with that draft.

**Validates: Requirements 3.5**

### Property 10: Section Source Attribution

*For any* draft section, it must have metadata linking it to the agent that generated the content.

**Validates: Requirements 3.6**

### Property 11: Reviewer Output Structure

*For any* reviewer agent execution, the output must contain a literature summary, citations, and identified research gaps.

**Validates: Requirements 4.2, 4.3, 4.5**

### Property 12: Methodology Proposal Presence

*For any* methodology agent execution, the output must contain at least one complete methodology proposal with described steps.

**Validates: Requirements 5.1, 5.4**

### Property 13: Limitations Section Content

*For any* generated draft, the Limitations section must contain content derived from the critic agent's output.

**Validates: Requirements 6.5**

### Property 14: Document Storage Round Trip

*For any* uploaded PDF document, storing it to S3 and then retrieving the S3 key must allow successful retrieval of the document.

**Validates: Requirements 7.4**

### Property 15: Referential Integrity Preservation

*For any* draft with associated source documents, deleting the draft should maintain referential integrity (either cascade delete or prevent deletion).

**Validates: Requirements 7.5**

### Property 16: Draft ID Uniqueness

*For any* draft generation request, the system must return a unique UUID that can be used to retrieve that specific draft.

**Validates: Requirements 8.2**

### Property 17: API Error Response Format

*For any* API error condition, the response must include an appropriate HTTP status code (4xx or 5xx) and a structured error message.

**Validates: Requirements 8.6**

### Property 18: Input Validation Rejection

*For any* invalid API input (empty topic, malformed UUID, invalid S3 key), the system must reject the request with a 400 status code and descriptive error message.

**Validates: Requirements 8.7, 11.3**

### Property 19: Agent Execution Order

*For any* draft generation, the execution timestamps in the audit trail must show Reviewer executed before Methodology, and Methodology executed before Critic.

**Validates: Requirements 9.1, 9.2, 9.3**

### Property 20: Draft Assembly Completeness

*For any* completed draft, the final output must contain content from all three agents (Reviewer, Methodology, Critic).

**Validates: Requirements 9.4**

### Property 21: Agent Failure Handling

*For any* simulated agent failure, the MCP must update the draft status to "failed", log the error to the database, and return an error response to the user.

**Validates: Requirements 9.5, 9.6**

### Property 22: Progress Event Creation

*For any* draft generation that takes longer than 10 seconds, the system must create at least one progress event in the execution_events table.

**Validates: Requirements 10.3**

### Property 23: LLM Retry Behavior

*For any* simulated LLM API failure, the system must retry exactly 3 times with exponentially increasing delays (1s, 2s, 4s) before failing.

**Validates: Requirements 10.5, 11.1**

### Property 24: Retry Exhaustion Error

*For any* LLM API call where all retries are exhausted, the system must return a descriptive error message indicating the failure reason.

**Validates: Requirements 11.2**

### Property 25: Error Logging Completeness

*For any* error that occurs during draft generation, an error record must be created in the execution_events table with error details.

**Validates: Requirements 11.4**

### Property 26: Database Reconnection Attempt

*For any* simulated database connection failure, the system must attempt to reconnect before failing the request.

**Validates: Requirements 11.5**

### Property 27: API Timeout Enforcement

*For any* external API call (LLM, S3), the system must enforce a timeout and fail the call if it exceeds the configured limit.

**Validates: Requirements 11.6**

### Edge Cases and Examples

The following scenarios should be tested as specific examples rather than universal properties:

**Example 1: Status Endpoint Functionality**
- Given a draft ID, the status endpoint should return the current status (pending, processing, completed, or failed)
- **Validates: Requirements 8.3**

**Example 2: Draft Retrieval Endpoint**
- Given a completed draft ID, the retrieval endpoint should return the complete draft with all sections
- **Validates: Requirements 8.4**

**Example 3: Audit Trail Endpoint**
- Given a draft ID, the audit trail endpoint should return all execution events and agent outputs
- **Validates: Requirements 8.5**

**Example 4: Empty Research Topic**
- Given an empty string as research topic, the API should reject with 400 status and error message "Research topic cannot be empty"
- **Validates: Requirements 8.7, 11.3**

**Example 5: Malformed Draft ID**
- Given a non-UUID string as draft ID, the API should reject with 400 status and error message "Invalid draft ID format"
- **Validates: Requirements 8.7, 11.3**

**Example 6: Non-existent Draft Retrieval**
- Given a valid UUID that doesn't exist in the database, the API should return 404 status with error message "Draft not found"
- **Validates: Requirements 8.6**
