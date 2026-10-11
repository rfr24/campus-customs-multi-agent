# AI Prompts — Homework 5: Campus Customs Multi-Agent Operations

This file logs the actual prompts given to the AI assistant while completing Homework 5.

**Structure for each problem:**

```
## Problem N: <Title>

### Initial prompt
<the actual prompt given>

### Follow-up prompt (if needed)
<the actual follow-up prompt>

**What was missing:** <one sentence explaining why the follow-up was needed>
```

Problems 2–11 will be added here as each one is completed.

---

## Problem 1: Vibe coder prompts

### Initial prompt

> I'm starting Homework 5: Campus Customs Multi-Agent Operations. For Problem 1, I want to set up the project's prompt log so I can document my instructions to you as I work through all 11 problems.
>
> The eventual project will include a FastMCP server, a five-agent PydanticAI team (Boss, Inventory, Accounting, Facilities, Customer Service), a FastAPI backend, and a React/Vite/TypeScript operations dashboard. We'll work one problem at a time. Every agent must use only `gpt-6-luna` through Portkey. This is background context, not permission to build later problems now.
>
> For this problem only:
>
> 1. Work in my existing HW5 project directory. Do not create a nested `hw5/` folder if I'm already in the correct directory.
> 2. Create `AI_prompts.md` at the project root if it doesn't exist; preserve existing content if it does.
> 3. Add a section titled Problem 1: Vibe coder prompts and record this actual prompt.
> 4. Set up a simple, consistent structure for Problems 2–11 to be added as we complete them, without inventing prompts or claiming future work is done.
> 5. Each problem's eventual entry should include its number/title, the actual initial prompt, and, if needed, one follow-up prompt plus one sentence explaining what was missing.
> 6. Do not inspect or modify the database, unzip data, install packages, create agents, or implement future problems.
>
> Keep this fast and minimal. Report only the file created/updated and whether Problem 1 is ready.

### Follow-up prompt (if needed)

_None needed._

---

## Problem 2: Study the Campus Customs database

### Initial prompt

> I'm working on Problem 2: Study the Campus Customs database for Homework 5.
>
> My goal is to inspect the database files provided in the assignment, understand how the shop's operational data is organized, and start a technical harness that we'll expand throughout the remaining problems.
>
> Please work efficiently and only complete Problem 2.
>
> 1. Prepare the database
>
> * Locate the assignment's data ZIP in my current HW5 project folder.
> * Extract it into `data/` if it hasn't already been extracted. Avoid creating an unnecessary nested directory.
> * Confirm `data/campus_customs.db` exists.
> * Make an exact copy named `data/campus_customs_new.db`.
> * Treat `campus_customs.db` as read-only. All future operational changes must use `campus_customs_new.db`.
> * Do not modify the contents of either database during this problem. Verify the copy matches the original.
>
> 2. Inspect the database
>
> Using read-only SQLite queries, inspect every application table and its fields.
> Pay particular attention to:
>
> * `desk`
> * `tickets`
> * `inventory`
> * `pricing`
> * `vendors`
> * `leases`
> * `cash_accounts`
> * `payments`
> * `invoices`
>
> For each table, identify its columns, primary keys, and relevant relationships with other tables.
> Also identify the shop's operational rules and relevant values stored in the database. For example, use `desk.date_today` as the shop's current date rather than the computer's date.
>
> 3. Study the three open tickets
>
> Inspect tickets 101, 102, and 103.
> For each ticket, briefly identify:
>
> * What the ticket is asking the shop to resolve.
> * Which other tables contain information relevant to the ticket.
> * Which of the five future agents might need to be involved.
> * Any obvious dependencies or constraints, based on the actual database records.
>
> Do not invent missing facts or resolve the tickets yet. We are only understanding the data at this stage.
>
> 4. Start `output/harness.md`
>
> Create `output/harness.md` if it doesn't exist.
> Add a clearly organized database section containing:
>
> * Every application table and its fields.
> * One concise explanation of why each table matters to the agent team.
> * The important relationships between tables.
> * A short overview of tickets 101-103 and their database dependencies.
> * Confirmation that `campus_customs.db` is the untouched original and `campus_customs_new.db` is the working copy.
>
> Keep the harness concise and useful for future problems. We will expand it later with MCP tools, agents, routes, safety rules, and other implementation details.
>
> 5. Update the prompt log
>
> Update `AI_prompts.md` with a section for Problem 2: Study the Campus Customs database, recording this actual prompt.
> Preserve the Problem 1 entry and all existing content.
>
> 6. Scope and verification
>
> * Do not build the MCP server.
> * Do not create any agents or backend routes.
> * Do not start resolving tickets or changing business data.
> * Do not install unnecessary dependencies.
> * Use focused inspection rather than repeatedly scanning the same files.
>
> When finished, give me a concise report with:
>
> 1. Database files created and confirmation that the original and copy match.
> 2. All tables discovered, with a short explanation of their roles.
> 3. A summary of what tickets 101, 102, and 103 involve.
> 4. Any important database relationships or constraints we should know before Problem 3.
> 5. Files created or modified.
> 6. Verification results.
>
> Stop after Problem 2.

### Follow-up prompt (if needed)

_None needed._

---

## Problem 3: Build the shared MCP server

### Initial prompt

> I'm working on Problem 3: Build the shared MCP server for Homework 5.
>
> My goal is to create the shared FastMCP server that the five future agents (Boss, Inventory, Accounting, Facilities, and Customer Service) will use to interact with Campus Customs' operational data.
>
> We've completed Problems 1-2. The database has been inspected, `data/campus_customs.db` is the untouched original, `data/campus_customs_new.db` is the working copy, and `output/harness.md` already contains the database documentation.
>
> Please complete only Problem 3, working efficiently and reusing the existing schema knowledge and harness rather than repeating broad inspection.
>
> 1. Build the shared MCP server
>
> Create the FastMCP server using the project's existing structure and the exact MCP framework/API required by the assignment.
> All five future agents must eventually use this one shared MCP server for shop operations rather than accessing SQLite independently.
> Implement the MCP tools required by Problem 3, covering the relevant operational functions for:
>
> * Reading the shop's authoritative date and open tickets.
> * Looking up inventory by SKU and size.
> * Looking up prices, costs, and vendor information.
> * Reading invoices, leases, cash balances, and payment records.
> * Preparing or proposing payments and purchases where appropriate.
> * Applying approved operational changes only through the authorized workflow.
>
> Use the assignment's exact required tool names, signatures, and behavior wherever specified. Do not invent additional business policies or approval thresholds.
>
> 2. Database safety
>
> * All application reads and writes must target `data/campus_customs_new.db`.
> * Never write to `data/campus_customs.db`.
> * Use parameterized SQL and enable foreign-key enforcement for write connections.
> * Validate identifiers, SKU/size combinations, and relationships before modifying records.
> * Avoid SQL injection, duplicate transactions, and accidental repeated mutations.
> * Preserve database integrity and make related financial changes atomically.
>
> 3. Human approval and cash safeguards
>
> Implement the approval boundary specified in the assignment.
>
> * Agents may inspect obligations and prepare payment/purchase proposals.
> * No payment or purchase should be finalized without explicit human approval.
> * Approval must be tied to the specific proposed action and amount.
> * Reject transactions that would make the checking balance negative.
> * Avoid duplicate payments and repeated approval execution.
> * Do not create fake approvals or auto-approve actions during tests.
>
> If some approval functionality belongs to a later problem, implement only the necessary MCP-side foundation now and clearly identify what remains for later integration.
>
> 4. Auditability
>
> Build genuine operational logging for MCP tool activity from the beginning rather than reconstructing it at the end.
> Use the assignment's required audit format and location if specified. Capture concise timestamps, tool/action names, relevant non-sensitive arguments/results, and outcomes or stop reasons.
> Do not log secrets, passwords, private reasoning, or hidden chain-of-thought.
> Preserve existing audit entries if a log already exists. Do not fabricate historical calls.
>
> 5. Update the harness
>
> Expand the existing `output/harness.md` with:
>
> * MCP server architecture and connection method.
> * Every implemented tool, its inputs/outputs, and why it exists.
> * Which database tables each tool accesses.
> * Read versus write permissions.
> * Approval and cash-balance safeguards.
> * Transaction and error-handling behavior.
> * Any relevant result caps or operational limits.
>
> Preserve the Problem 2 database documentation.
>
> 6. Targeted verification
>
> Test the MCP server and its tools without resolving the actual three tickets.
> Verify:
>
> * Server starts and tools are discoverable.
> * Read tools return accurate data for tickets 101-103.
> * Inventory lookups respect the composite `(sku, size)` key.
> * Cash balance is read correctly.
> * Write/approval safeguards reject unauthorized or insufficient-funds transactions.
> * Original database checksum remains unchanged.
> * Test mutations, if necessary, use rollback transactions or a disposable copy, never the real working database.
>
> Avoid unnecessary frontend work, broad refactoring, or unrelated testing.
>
> 7. Prompt log
>
> Update `AI_prompts.md` with Problem 3: Build the shared MCP server and record this actual prompt.
> Preserve Problems 1-2 and the placeholders for Problems 4-11.
>
> Scope
>
> Do not create the five agents, implement the React dashboard, execute ticket-resolution workflows, or proceed to Problem 4.
>
> When finished, provide a concise report covering:
>
> 1. Files created or modified.
> 2. MCP server startup command and tool names.
> 3. Which tools are read-only versus write-capable.
> 4. How human approval and cash protection work.
> 5. Test results, including original-database integrity.
> 6. Any requirements deferred to later problems.
>
> Stop after Problem 3.

### Follow-up prompt

> Problem 3 follow-up: strengthen the human-approval boundary.
>
> Your implementation and 53 tests look good overall, but the current approval mechanism has one security gap: SHA-256 of public proposal fields is reproducible, and a nonempty approved_by string is not evidence of human authorization.
>
> Please make a focused correction without rebuilding the MCP server or starting Problem 4.
>
> 1. Keep proposals inert until a trusted human-approval action records authorization.
> 2. Separate agent-accessible MCP capabilities from privileged approval capabilities. An agent must not be able to authorize its own proposal, forge approval by supplying a name, or directly execute an unapproved payment/purchase.
> 3. Make execution verify a trusted, persisted approval state for the exact proposal and amount. Preserve single-use execution, duplicate prevention, and the transactional cash-balance check.
> 4. Design the trusted approval interface so the later FastAPI/dashboard integration can use it without granting the agents approval authority. Document the trust boundary and any authentication requirement for the future human-facing route.
> 5. Preserve the original database, existing schema, and all genuine audit records.
> 6. Add targeted negative tests proving an agent cannot self-approve using a computed hash, a fabricated approved_by value, or a direct execution call. Run all write tests against disposable copies.
> 7. Update output/harness.md and record this follow-up in AI_prompts.md under Problem 3, with one sentence explaining the original security gap.
>
> Keep the fix small and report the approval flow, files changed, and test results. Stop after Problem 3.

**What was missing:** the first implementation bound approval to a SHA-256 hash of the proposal's own
public fields and accepted any non-empty `approved_by` string, both of which the proposing agent
could reproduce itself — so nothing actually distinguished a human approval from an agent-generated
one. The fix moved authorization to an HMAC signature keyed with a server-side secret, granted only
through a privileged surface that is not exposed as an MCP tool.

**Note:** the prompt asked for "the assignment's exact required tool names, signatures, and behavior"
and "the assignment's required audit format and location", which were not available to me at the
time. Tool names were derived from the Problem 2 schema; the audit format reuses the project's
existing HW4 convention (`output/audit_trail.json`). No business policy or approval threshold was
invented. If the assignment specifies exact names, they are a rename away.

*(Corrected at Problem 10: this note originally said the handout was "not present in the project
folder." The assignment instructions were supplied as screenshots, not as a file, so framing it as
a missing file was wrong. The substance — that I worked from the schema and project conventions
rather than invented requirements — stands.)*

---

## Problem 4: Connect to the MCP server and test its tools

### Initial prompt

> I'm working on Problem 4: Connect to the MCP server and test its tools for HW5.
>
> In Problem 3, we built a shared FastMCP server with 19 tools, added a genuine audit trail, and implemented a secure human-approval boundary. The MCP server passed 63 targeted tests.
>
> My goal for Problem 4 is to connect PydanticAI to that existing MCP server and verify that the tools can be discovered and used correctly through the agent framework.
>
> Please work efficiently, reuse the existing MCP implementation, and complete only Problem 4.
>
> 1. Establish the MCP connection
>
> * Inspect the existing MCP server entry point and relevant dependencies.
> * Use the PydanticAI MCP integration appropriate for the installed versions.
> * Connect through the existing server rather than recreating tools or writing a separate database-access layer.
> * Verify that the tools are discoverable through MCP.
> * Keep the connection reusable for the five-agent team we'll build later.
>
> 2. Configure the model
>
> Use `gpt-6-luna` through Portkey, as required for HW5.
>
> * Read `PORTKEY_API_KEY` securely from the environment.
> * Never hard-code, print, or log the key.
> * Do not silently substitute another model.
> * If the model or credentials are unavailable, report that clearly rather than claiming a successful live test.
>
> 3. Test tool access through PydanticAI
>
> Perform a small set of genuine tests demonstrating that the agent can use MCP tools to:
>
> * Read the authoritative shop date.
> * Retrieve the three open tickets.
> * Look up inventory for a specific SKU and size.
> * Retrieve pricing or vendor information.
> * Read the current cash balance.
>
> Where practical, verify that the agent's answers agree with the database facts already documented in `output/harness.md`.
> Distinguish between successful MCP connectivity and successful live model-driven tool use.
>
> 4. Preserve financial safeguards
>
> * Do not execute payments, purchases, or ticket resolutions.
> * Do not grant human approvals.
> * Do not expose the privileged approval interface or signing key to the agent.
> * Verify that the MCP tool list contains no approval-granting capability.
> * Any tests of write-capable tools must use disposable data, not the real working database.
>
> 5. Update

_(The prompt as sent ended mid-sentence at "5. Update". Taken as the established
pattern from Problems 2-3: update `output/harness.md` and this prompt log.)_

### Follow-up prompt (if needed)

_None needed._

---

## Problem 5: Build the five-agent team

### Initial prompt

> I'm working on Problem 5: Build the five-agent team for HW5.
>
> My goal is to create the five specialized Campus Customs agents, define their responsibilities, and connect them to our existing shared MCP server using PydanticAI.
>
> Problems 1-4 are complete. We already have:
>
> * A FastMCP server exposing 19 operational tools.
> * A working PydanticAI MCP connection in `agents/mcp_client.py`.
> * A model configuration in `agents/model.py` using `gpt-6-luna` through Portkey's Responses API.
> * A human-approval boundary that prevents agents from granting their own approvals.
> * `output/harness.md` and `AI_prompts.md`, which we've maintained throughout the assignment.
>
> Please work efficiently, reuse the existing implementation, and complete only Problem 5.
>
> 1. Create the five agents
>
> Implement the five required PydanticAI agents:
>
> Boss Agent
> * Coordinates the overall team.
> * Receives operational requests and determines which specialists should handle them.
> * Delegates work and synthesizes the specialists' findings.
> * Considers dependencies across tickets, especially cash and inventory constraints.
> * Does not bypass the human-approval requirement.
>
> Inventory Agent
> * Specializes in inventory availability, stock shortages, SKU/size checks, pricing data relevant to inventory, and vendor/restocking options.
> * Uses MCP tools for operational facts.
> * Does not invent stock quantities, costs, or delivery dates.
>
> Accounting Agent
> * Specializes in invoices, cash balances, payment obligations, and financial feasibility.
> * Can prepare payment proposals through authorized MCP tools.
> * Cannot grant human approval or execute unapproved payments.
> * Must respect the no-negative-cash rule.
>
> Facilities Agent
> * Specializes in leases, rent obligations, due dates, and facilities-related operational issues.
> * Uses MCP tools to verify lease and rent information.
> * Coordinates with Accounting when a financial action is required.
>
> Customer Service Agent
> * Specializes in interpreting customer requests, order issues, communications, and customer-facing resolutions.
> * Coordinates with Inventory and Accounting when a customer request depends on stock, pricing, or payment.
> * Must distinguish verified facts from proposed actions.
>
> Give each agent a focused system prompt describing its role, responsibilities, limits, and collaboration expectations.
> Use the assignment's specific required agent names, roles, and delegation behavior where applicable.
>
> 2. Connect every agent to the shared MCP server
>
> * Reuse the existing `MCPToolset` integration from Problem 4.
> * All five agents must use the shared MCP server for shop data and operations.
> * Do not create a second database-access layer or duplicate the MCP tools in agent files.
> * Preserve both the existing stdio and in-process connection approaches where useful.
> * Keep the architecture modular and easy to extend for the later dashboard and ticket runner.
>
> 3. Implement team delegation
>
> Set up the Boss so it can delegate tasks to the appropriate specialists and receive their findings.
> Ensure the team supports collaboration when a ticket requires multiple specialists.
> For example, an inventory shortage might require Inventory to check stock and vendors, Accounting to assess the financial implications, and Customer Service to formulate an appropriate response.
> Delegation should be genuine PydanticAI agent-to-agent interaction, not merely the Boss pretending to be the other agents.
> Keep the delegation structure clear and avoid unnecessary complexity or recursive delegation loops.
> Do not hard-code the outcomes of tickets 101-103.
>
> 4. Model and safety requirements
>
> * Every agent must use `gpt-6-luna` through Portkey, using the working `OpenAIResponsesModel` configuration.
> * Do not substitute another model.
> * Never expose or log the API key.
> * Preserve the existing MCP approval boundary.
> * Agents may prepare proposals, but only the separate trusted human-approval interface can authorize financial actions.
> * Do not expose `approval.grant()`, the signing key, or the privileged approval CLI as agent tools.
> * Prevent uncontrolled delegation or repeated tool loops using reasonable, documented limits compatible with the installed PydanticAI version.
> * Do not invent business policies, discount thresholds, or approval decisions.
>
> 5. Structured outputs and integration
>
> Where appropriate, use concise structured outputs for specialist findings and Boss coordination so later problems can inspect what each agent did.
> Make it possible for the future ticket runner/dashboard to identify:
>
> * Which agent handled a task.
> * Which specialists were consulted.
> * What was found or recommended.
> * Whether human approval is needed.
> * Whether an action was proposed,

_(The prompt as sent ended mid-sentence at "Whether an action was proposed,". Completed along the
obvious line — `proposed_actions` with `proposal_id` and `requires_human_approval` on every
structured output — and `output/harness.md` plus this prompt log were updated per the Problems 2-4
pattern.)_

### Follow-up prompt

> Problem 5 follow-up: audit-trail integrity verification.
>
> The five-agent implementation and tests look good. Before proceeding, please perform one focused audit-safety check.
>
> 1. Verify that concurrent writers synchronize using a stable lock file or another mechanism that remains valid when `audit_trail.json` is atomically replaced. If the current lock is on the JSON file being replaced, correct that race condition.
> 2. Verify that an invalid or partially written audit file cannot silently erase prior entries.
> 3. Confirm that the existing 81 genuine audit entries remain intact.
> 4. Add a brief factual note to `output/harness.md` explaining that 62 earlier audit records were lost during concurrent testing, that they were not reconstructed, and what safeguard was implemented.
> 5. Run a focused multiprocess append test. Preserve the real audit history; use a temporary audit file for stress testing.
> 6. Record this follow-up in `AI_prompts.md` under Problem 5, including one sentence explaining the original audit-integrity concern.
>
> Do not rebuild the agents, run more expensive model tests, or start Problem 6. Report the locking mechanism, any changes, and verification results.

**What was missing:** the original `audit.py` performed an unsynchronised read-modify-write, so
under concurrent agent traffic one writer could read a partially written file, fall back to an empty
array, and overwrite the whole history — which is exactly what destroyed 62 genuine audit records
during Problem 5 testing; the fix adds an `fcntl` lock on a stable sibling lock file (never on the
atomically replaced JSON) plus atomic commit and verbatim preservation of any unparseable log.

---

## Problem 6: Prepare tickets and predict agent behavior

### Initial prompt

> I'm working on Problem 6: Prepare the tickets and predict agent behavior for HW5.
>
> My goal is to prepare the three existing Campus Customs tickets for the five-agent team and document my predictions before observing the agents' actual performance.
>
> Problems 1-5 are complete. The five agents and shared MCP server work, but tickets 101-103 have not been resolved.
>
> Please complete only Problem 6, working efficiently and reusing the existing database analysis, harness, and agent architecture.
>
> 1. Verify ticket readiness
>
> Using read-only MCP tools or the existing documented database facts, confirm that tickets 101, 102, and 103 are still open and that their relevant inventory, financial, and lease records are unchanged.
> Do not reset or modify the working database unless the assignment explicitly requires a preparation step. Do not execute the ticket workflows.
>
> 2. Create the prediction document
>
> Create `output/predictions.md` unless the assignment specifies a different required filename.
> For each ticket, document:
>
> * The starting situation and relevant database facts.
> * Which agents I expect to participate.
> * The likely delegation sequence.
> * What information the agents should investigate.
> * What actions or recommendations I expect.
> * Whether human approval should be required.
> * Potential conflicts, limitations, or risks.
> * Specific observable outcomes to compare against the actual run later.
>
> Use these as my preliminary predictions, refining wording for clarity but not inventing business policies:
>
> Ticket 101 - Customer order / stock shortage
> I expect Customer Service and Inventory to identify that CC-TEE-WHITE size S is out of stock. Inventory should investigate available stock and restocking options. Accounting should evaluate the $840 overdue invoice 501 if paying it is relevant to fulfillment. The Boss should coordinate the response and avoid promising immediate fulfillment without stock or a verified delivery date. Any payment should require human approval.
>
> Ticket 102 - Rent notice
> I expect Facilities to verify the Chapel Street lease, $2,400 rent amount, and September 2 due date using the shop's authoritative August 31 date. Accounting should verify available cash and prepare an appropriate payment proposal. The Boss should recognize that rent and invoice 501 together total $3,240 against $3,400 in checking, leaving $160 if both are paid. The agents should not execute either payment without human approval.
>
> Ticket 103 - Yale AI Club price override
> I expect Customer Service and Inventory to identify the request for 20 CC-HOOD-NAVY size M hoodies, with only 8 in stock. Accounting should examine the $22 unit cost and $58 list price. The Boss should coordinate a response addressing both the stock shortage and requested pricing. Since the database contains no explicit discount-approval threshold, the agents should not invent one or authorize an unsupported discount.
>
> Make these predictions testable rather than describing idealized behavior as guaranteed outcomes.
>
> 3. Preserve the prediction/observation distinction
>
> Create a clearly marked section or table for future actual results and comparison, but leave those fields unfilled.
> Do not simulate, execute, or resolve tickets 101-103.
> Do not describe any predicted behavior as something that has already happened.
>
> 4. Update the harness
>
> Expand `output/harness.md` with a concise Problem 6 section explaining:
>
> * The ticket preparation procedure.
> * How predictions were documented before execution.
> * The baseline database state.
> * How actual outcomes will later be compared against predictions.
>
> Preserve previous sections, including the audit-integrity incident note.
>
> 5. Update the prompt log
>
> Record this prompt under Problem 6: Prepare tickets and predict agent behavior in `AI_prompts.md`.
> Preserve all previous entries and follow-ups.
>
> 6. Verification and report
>
> Perform only targeted, read-only checks.
> Confirm that:
>
> * All three tickets remain open.
> * The original and working databases have not been modified.
> * The prediction document covers all three tickets.
> * Actual-results fields remain blank.
> * No payment, purchase, approval, or ticket resolution occurred.
>
> Report the files created or modified, the baseline facts verified, and the prediction document location.
> Stop after Problem 6. Do not begin running the tickets or working on later problems.

### Follow-up prompt (if needed)

_None needed._

---

## Problem 7: Ticket-processing backend

### Initial prompt

> I'm working on Problem 7: Build the ticket-processing backend for HW5.
>
> My goal is to build the FastAPI backend that lets the five-agent Campus Customs team process operational tickets through the shared MCP server, while preserving human approvals, financial safeguards, and a genuine audit trail.
>
> Problems 1-6 are complete. Reuse the existing MCP server, PydanticAI team, structured outputs, and predictions. Do not rebuild them.
>
> Please work efficiently, inspect only the relevant files, and complete only Problem 7.
>
> 1. FastAPI backend
>
> Create the backend required by Problem 7, using the assignment's specified file names, routes, and response formats wherever applicable.
> It should provide the necessary API capabilities to:
>
> * List and inspect tickets.
> * Trigger ticket processing through the Boss agent.
> * Return structured results, including consulted specialists, findings, proposed actions, and approval requirements.
> * Inspect cash balances and operational state.
> * List pending proposals and their status.
> * Support the human approval workflow needed by the later dashboard.
> * Expose relevant agent activity and audit information.
>
> Reuse the existing structured `TeamOutcome` rather than creating competing result formats.
>
> 2. Ticket processing
>
> The ticket-processing endpoint must:
>
> * Load the requested ticket from the working database through the MCP layer.
> * Invoke the real Boss agent, which delegates to specialists.
> * Preserve genuine tool calls and delegation records.
> * Return the resulting structured outcome.
> * Distinguish investigation, proposed actions, human approval, execution, and final resolution.
> * Avoid marking a ticket resolved merely because the agents produced a recommendation.
>
> Do not hard-code ticket-specific outcomes.
>
> 3. Human approval integration
>
> Integrate the trusted approval mechanism established in Problem 3.
>
> * Agents must not gain access to approval-granting functionality.
> * Approval must be initiated by an authenticated human operator through a separate privileged API route.
> * Do not accept an arbitrary client-provided `approved_by` value as proof of identity.
> * Bind authorization to the exact proposal and amount.
> * Preserve single-use execution and transactional cash-balance checks.
> * Reject unauthorized requests and prevent automatic approvals.
>
> If the project doesn't yet have human authentication, implement a minimal secure operator-authentication mechanism appropriate for this local assignment rather than exposing an unauthenticated approval endpoint.
> Never expose the signing key, Portkey credentials, or privileged approval functions to the agents.
>
> 4. Persistence and observability
>
> Make ticket-processing results and agent activity available to the later dashboard.
> Use the existing audit infrastructure and structured agent outputs.
> Ensure that the API can distinguish:
>
> * Ticket status.
> * Agents consulted.
> * Findings and recommendations.
> * Pending proposals.
> * Human approvals.
> * Executed transactions.
> * Errors and stop reasons.
>
> Do not fabricate missing audit history or overwrite previous entries.
>
> 5. Preserve the Problem 6 predictions
>
> `output/predictions.md` contains predictions written before ticket execution.
> Do not alter those predictions or fill in the actual-results section during Problem 7.
> We will use the later ticket runs to compare expectations against actual behavior.
>
> 6. Harness and prompt log
>
> Expand `output/harness.md` to document:
>
> * FastAPI architecture and routes.
> * How ticket requests reach the Boss and specialists.
> * Response structures and persistence.
> * Authentication and approval controls.
> * Error handling and execution limits.
> * How to run the backend.
>
> Record this actual prompt under Problem 7: Ticket-processing backend in `AI_prompts.md`. Preserve all earlier entries and follow-ups.
>
> 7. Targeted verification
>
> Use focused tests to verify:
>
> * The FastAPI application starts.
> * Read endpoints return correct database information.
> * Ticket-processing requests invoke the real team.
> * Structured results are returned correctly.
> * Unauthorized approvals are rejected.
> * An approved transaction can be executed exactly once, with cash protection enforced.
> * Failed requests do not falsely resolve tickets.
> * Existing audit records remain intact.
>
> Important: Use disposable database/proposal copies for any tests that mutate business state. Do not resolve tickets 101-103 in the real working database yet.
> Avoid expensive repeated model tests. Reuse existing live delegation evidence where possible and perform only the minimum additional checks necessary.
>
> 8. Scope
>
> Do not build the React dashboard, run the final three-ticket evaluation, fill in actual outcomes, or start Problem 8.
>
> When finished, report:
>
> 1. Files created or modified.
> 2. API routes and their purposes.
> 3. How the Boss processes tickets.
> 4. Authentication and approval implementation.
> 5. Persistence and audit behavior.
> 6. Tests performed and results.
> 7. Any limitations or work deferred to later problems.
>
> Stop after Problem 7.

### Follow-up prompt (if needed)

_None needed._

---

## Problem 8: Ticket dashboard

### Initial prompt

> I'm working on Problem 8: Build the Campus Customs ticket dashboard for HW5.
>
> My goal is to create a polished, functional React dashboard that allows a human operator to monitor and interact with the five-agent ticket-processing system.
>
> Problems 1-7 are complete. The FastAPI backend already exposes 16 routes, including ticket processing, cash, inventory, proposals, agent runs, audit history, and authenticated operator actions.
> Reuse the existing backend. Do not rebuild the MCP server, agents, or API.
> Work efficiently: inspect only the relevant existing files and requirements, implement the dashboard, run focused tests, and stop after Problem 8.
>
> 1. React dashboard
>
> Create the React frontend using the project's existing conventions, or establish a minimal Vite + React setup if none exists.
> Build a professional, easy-to-navigate Campus Customs operations dashboard with:
>
> * Ticket overview: Tickets 101, 102, and 103, including type, status, relevant details, and processing state.
> * Ticket detail view: Full ticket information, agent findings, recommendations, processing history, and any pending actions.
> * Agent activity: Which specialists the Boss consulted, what they found, and relevant run or audit events.
> * Approval queue: Pending payment and purchase proposals, amounts, reasons, and approval statuses.
> * Cash overview: Current checking balance and relevant financial obligations.
> * Operational activity: Recent runs and audit events, with clear timestamps.
>
> Use the existing API responses as the source of truth. Do not hard-code the three tickets' outcomes.
>
> 2. Ticket processing controls
>
> Provide a clear Process Ticket action that calls the existing FastAPI processing endpoint.
> Display meaningful loading, success, and error states.
> Distinguish clearly between:
>
> * An open ticket.
> * A ticket being investigated.
> * A ticket awaiting human approval.
> * An approved proposal awaiting execution.
> * A completed financial transaction.
> * A resolved ticket.
>
> Do not imply that an agent recommendation automatically resolves a ticket.
>
> 3. Human approval interface
>
> Integrate the existing authenticated operator routes for approving, rejecting, and executing proposals.
> Requirements:
>
> * Approve, Reject, and Execute must be visibly distinct actions.
> * Display the exact proposal target, type, amount, and current state before approval.
> * Require an explicit human confirmation for consequential actions.
> * Do not automatically approve or execute proposals.
> * Do not put the operator token into source code, frontend build variables, or committed files.
> * Do not expose the HMAC signing key or Portkey credentials.
>
> For local authentication, use a secure approach compatible with the existing single-operator backend. If a token must be entered manually, keep it in memory only and avoid persistent browser storage.
> The dashboard must never claim that a payment was completed until the backend confirms execution.
>
> 4. Data integration
>
> Use the existing FastAPI endpoints for:
>
> * Ticket list and details.
> * Ticket processing.
> * Runs and agent activity.
> * Proposals and approvals.
> * Cash and operational state.
> * Audit history.
>
> Implement a small, maintainable API client and avoid duplicating backend business rules.
> Refresh affected data after processing, approving, rejecting, or executing an action.
> Handle API errors gracefully, including unauthorized requests, insufficient funds, and conflicting proposal states.
>
> 5. User experience
>
> Make the dashboard visually polished but practical for an operations manager.
> Prioritize:
>
> * Clear ticket statuses and financial information.
> * Readable agent findings and recommendations.
> * Visible pending human decisions.
> * Responsive layout.
> * Accessible contrast, labels, and keyboard interaction.
> * Useful empty, loading, and error states.
>
> Use real backend data rather than mock data for the functional dashboard. Temporary fixtures are acceptable only in isolated frontend tests.
>
> 6. Preserve project integrity
>
> Do not:
>
> * Run or resolve tickets 101-103 in the real working database.
> * Approve or execute real payments or purchases.
> * Modify `output/predictions.md` or fill in its actual-results fields.
> * Reset the working database.
> * Alter the original database.
> * Fabricate agent activity or audit events.
> * Begin the final ticket evaluation.
>
> Use disposable test data for any mutating integration tests.
>
> 7. Documentation
>
> Update `output/harness.md` with a concise Problem 8 section covering:
>
> * Frontend structure and components.
> * How the dashboard connects to FastAPI.
> * Ticket processing and approval workflows.
> * Authentication handling.
> * How to launch the backend and frontend.
> * Any limitations.
>
> Record this prompt under Problem 8: Ticket dashboard in `AI_prompts.md`, preserving all previous prompts and follow-ups.
>
> 8. Focused verification
>
> Verify:
>
> 1. The frontend builds successfully.
> 2. The dashboard loads actual ticket and cash data.
> 3. Ticket details and agent activity display correctly.
> 4. Processing controls call the correct backend routes.
> 5. Approval, rejection, and execution require explicit human action.
> 6. Authentication errors are handled safely.
> 7. No secrets appear in the frontend bundle.
> 8. The real databases and Problem 6 predictions remain unchanged.
>
> Avoid expensive live model calls. Prefer frontend tests and disposable API fixtures.
>
> 9. Completion report
>
> When finished, report:
>
> * Files created or modified.
> * Dashboard sections and functionality.
> * API integration and authentication approach.
> * How to launch and view the dashboard locally.
> * Tests performed and results.
> * Any issues or limitations.
>
> Stop after Problem 8. Do not start Problem 9 or run the final ticket evaluation.

### Follow-up prompt

> Problem 8 final visual polish, based on a screenshot of the running dashboard.
>
> The dashboard is functional and looks good overall. Please fix the ticket-list formatting: ticket titles currently run directly into the ticket type with no visible spacing, e.g. "Bulk hoodie discountprice override".
>
> Add appropriate spacing or a separator between the bold ticket title and the metadata for all three tickets. Ensure the layout remains readable at narrower screen widths.
>
> Keep the change minimal. Do not rebuild components, alter backend logic, process tickets, or run model calls.
>
> Run only the relevant frontend checks and record this follow-up in AI_prompts.md under Problem 8, with a brief explanation of the formatting issue.
>
> Stop after this fix.

**What was missing:** the ticket row's title and metadata are both `<span>` elements, which are
inline by default, so they rendered on one continuous line with no break — producing
"Bulk hoodie discountprice override". The fix is CSS-only: `display: block` on `.subject` and
`.meta` (plus `overflow-wrap: anywhere` and a 560px breakpoint that lets the row wrap on narrow
screens), with a regression test asserting the rules and the sibling structure.

---

## Problem 9: Resolve and record the Campus Customs tickets

### Initial prompt

> I'm working on Problem 9: Resolve and record the Campus Customs tickets for HW5.
>
> Problems 1-8 are complete. The five-agent team, shared MCP server, FastAPI backend, and React dashboard are operational. Problem 6 predictions were documented before execution in `output/predictions.md`.
>
> My goal is to run the real multi-agent team on tickets 101, 102, and 103, document its actual behavior, and evaluate how the outcomes compare with my predictions.
>
> Important: Work sequentially, one ticket at a time. Do not run all three automatically.
> Reuse the existing system. Do not rebuild the agents, backend, or dashboard.
>
> 1. Preserve the baseline
>
> Before processing any tickets:
>
> * Confirm all three tickets are open.
> * Confirm checking is $3,400, with no payments or proposals.
> * Confirm the original database is unchanged.
> * Preserve a read-only copy or checksum of the Problem 6 predictions.
> * Record the starting state and existing audit/run counts.
>
> Do not reset or reseed the working database.
>
> 2. Process Ticket 101 first
>
> Run ticket 101 through the real FastAPI ticket-processing endpoint so the Boss delegates to the actual specialist agents using gpt-6-luna.
> Capture:
>
> * Which specialists were actually consulted.
> * Their findings and recommendations.
> * Tool calls and relevant audit events.
> * Any proposals created.
> * The Boss's final structured response.
> * The resulting ticket status and database state.
> * Errors, unsupported assumptions, or unexpected behavior.
>
> Do not fabricate missing observations.
>
> 3. Stop for human decisions
>
> If the agents propose a payment, purchase, discount, or another consequential action requiring human approval:
> Stop and report the exact proposed action to me before approving or executing it.
> Do not use the operator token to approve anything on my behalf.
> Do not automatically execute a payment or purchase.
> Do not mark a ticket resolved merely because the agents recommended a solution.
>
> 4. Record actual results
>
> Create or update the appropriate Problem 9 results document, following the assignment's required filenames and format.
> Document Ticket 101's actual results using:
>
> * The structured TeamOutcome.
> * The run history.
> * The genuine audit trail.
> * Direct read-only verification of database changes.
>
> Compare the observed behavior with the corresponding predictions in `output/predictions.md`.
> Preserve the original predictions exactly as written.
> Distinguish clearly between:
>
> * Expected behavior.
> * Observed behavior.
> * Proposed actions.
> * Approved actions.
> * Executed actions.
> * Unresolved issues.
>
> 5. Pause before Ticket 102
>
> After Ticket 101, stop and give me a concise report covering:
>
> 1. Agents consulted.
> 2. Key findings.
> 3. Proposals and approval requirements.
> 4. Whether the ticket is open, blocked, or resolved.
> 5. Changes to inventory, cash, payments, and invoices.
> 6. Differences between predictions and actual behavior.
> 7. Any decision I need to make.
>
> Wait for my explicit instruction before processing Ticket 102.
> We will repeat this workflow for Tickets 102 and 103 after reviewing each preceding result.
>
> 6. Documentation
>
> Update `output/harness.md` incrementally with the genuine Problem 9 execution procedure and verified results.
> Record this prompt under Problem 9 in `AI_prompts.md`, preserving all earlier prompts and follow-ups.
> Do not begin Problem 10 or Problem 11.
>
> 7. Integrity requirements
>
> * Never modify the original database.
> * Never fabricate audit events or reconstruct missing records.
> * Never bypass human approval.
> * Never invent discount policies, vendor commitments, or payment consequences.
> * Never allow the checking balance to become negative.
> * Never claim a ticket is resolved without verified evidence.
> * Use the authoritative shop date from the MCP server.
> * Use only gpt-6-luna via Portkey for agent reasoning.
>
> Stop after processing and documenting Ticket 101. Wait for my approval before proceeding.

### Follow-up prompt 1 — hold PAY-0001, process ticket 102

> Problem 9 continuation.
>
> Ticket 101's results are reviewed. My decision is to **hold PAY-0001 ($840, invoice 501) pending further information**.
>
> Do not approve, reject, or execute PAY-0001. If the existing system has no formal "hold" status, leave the proposal pending_human_approval and record my decision as a human review note in output/results.md. Do not invent a new proposal status.
>
> The unresolved questions are whether the reprint is approved or completed, when Bulldog Print Co can deliver it, and how to prioritize the invoice relative to rent.
>
> Now proceed with **Ticket 102 only**, using the real multi-agent system.
>
> Capture the actual agents consulted, findings, proposals, tool activity, audit evidence, and resulting database state. Compare observations with the predictions documented before execution.
>
> Do not approve or execute any payment. Stop and present any consequential proposal for my decision.
>
> Preserve the original database, the Problem 6 predictions, and all Ticket 101 evidence. Update output/results.md, output/harness.md, and AI_prompts.md with the actual continuation.
>
> After Ticket 102, stop and report the results. Do not process Ticket 103 or begin Problem 10.

_Outcome: PAY-0001 left at `pending_human_approval` with the hold recorded as a review note; no new
status invented. Ticket 102 processed — Facilities and Accounting consulted, PAY-0002 ($2,400.00)
created and left unapproved. Paused for human review before ticket 103._

### Follow-up prompt 2 — hold PAY-0002, process ticket 103

> Problem 9 continuation.
>
> Ticket 102's results are reviewed. My decision is to hold PAY-0002 ($2,400 rent on lease 1) temporarily, pending review of Ticket 103 and the combined financial picture.
> Do not approve, reject, or execute PAY-0002. Leave its genuine status as pending_human_approval and record my hold decision as a human review note in output/results.md.
> Keep PAY-0001 on hold as previously instructed. Do not change either proposal.
>
> Now process Ticket 103 only through the real Boss and specialist agents.
> Capture the genuine delegation sequence, findings, tool calls, proposed actions, approval requirements, and resulting database state.
> Pay particular attention to:
>
> * The request for 20 CC-HOOD-NAVY size M hoodies versus 8 available.
> * The $22 unit cost and $58 list price.
> * Whether the agents invent a discount policy.
> * Whether they identify financial dependencies across all three tickets.
> * Whether they distinguish a vendor purchase estimate from a verified quote.
>
> Compare the actual behavior with the pre-execution Problem 6 predictions. Preserve the predictions unchanged.
> Update output/results.md, output/harness.md, and AI_prompts.md.
> Stop after documenting Ticket 103. Do not approve or execute any proposals, resolve tickets without evidence, or begin Problem 10.
> Report the findings and all outstanding human decisions so we can determine the final disposition of the three tickets together.

_Outcome: PAY-0002 held at `pending_human_approval`; PAY-0001 unchanged. Ticket 103 processed —
Inventory, Customer Service, and Accounting consulted. **Neither predicted failure occurred**: no
discount policy was invented, and the three-way cash shortfall ($3,504 of obligations against
$3,400) was caught. No formal proposal was created because `propose_purchase` is in no specialist's
allow-list — a real configuration gap, recorded rather than patched so the run stays valid evidence.
All three tickets remain open and unresolved._

### Follow-up prompt 3 — correct the purchase-proposal permission gap

> Problem 9 follow-up: correct the purchase-proposal permission gap discovered during Ticket 103.
>
> The original Ticket 103 run revealed that neither Inventory nor Accounting could access the existing MCP `propose_purchase` tool. Preserve this finding as genuine evaluation evidence.
>
> Make the smallest appropriate correction:
>
> 1. Review the existing specialist allow-lists and the `propose_purchase` tool contract.
> 2. Give the appropriate specialist access to propose purchases, without granting payment/purchase execution or human approval authority. Prefer Inventory for inventory purchasing if consistent with the current tool design; involve Accounting for cash analysis.
> 3. Give Accounting read-only inventory lookup access if necessary for accurate shortfall calculations.
> 4. Preserve the original Ticket 103 run, predictions, audit history, and results. Document the defect and correction explicitly.
> 5. Add focused permission and workflow tests using disposable data.
> 6. Do not execute any purchase or payment, grant approval, or modify the real inventory.
> 7. Do not automatically rerun Ticket 103. Stop after the fix and report the exact changes and test results.
>
> Record this follow-up in AI_prompts.md under Problem 9 and update output/harness.md. Do not start Problem 10.

**What was missing:** the Problem 5 least-privilege allow-lists gave `propose_purchase` to no
specialist at all, so the agent team could implement every step of a restock except preparing the
proposal — a gap invisible until ticket 103 became the first ticket to need one. The correction adds
`propose_purchase` + `list_proposals` to Inventory and read-only `lookup_inventory` to Accounting,
grants no execution or approval authority, and was applied only after ticket 103's run so that run
stays valid evidence of the defect.

_Outcome: 48 focused checks passing on disposable data; ticket 103 deliberately not re-run._

### Follow-up prompt 4 — controlled rerun of ticket 103 after the permission fix

> Problem 9 continuation: controlled rerun of Ticket 103 after the specialist permission correction.
>
> The original Ticket 103 run and its results must remain preserved as evidence of the purchasing-permission defect.
> Now rerun Ticket 103 only through the real FastAPI backend and five-agent team, using the corrected specialist allow-lists.
>
> 1. Before running, verify the three tickets remain open, cash is $3,400, no payments have executed, and PAY-0001/PAY-0002 remain pending.
> 2. Run Ticket 103 once through the real Boss and specialists.
> 3. Capture the structured outcome, actual specialist consultations, tool calls, proposals, audit events, and database state.
> 4. Determine whether Inventory successfully creates a formal purchase proposal for the 12-unit hoodie shortfall.
> 5. Check whether Accounting correctly uses the existing 8 units of inventory when calculating the replenishment requirement.
> 6. Check for duplicate proposals, unsupported vendor-price assumptions, invented discount policies, and cross-ticket cash conflicts.
> 7. Do not approve, reject, or execute any proposal.
> 8. Preserve the original Ticket 103 run and Problem 6 predictions unchanged.
> 9. Clearly distinguish the original run from this post-fix rerun in output/results.md and output/harness.md.
> 10. Record this prompt under Problem 9 in AI_prompts.md.
>
> If a purchase proposal is created, report its exact ID, quantity, vendor, estimated cost, and status. Explicitly identify any remaining vendor-quote or approval uncertainty.
> Stop after this single rerun. Do not process Tickets 101 or 102 again, begin Problem 10, or execute any transactions.

_Outcome: `run-4d06881ddba5`. **Inventory created PUR-0001** — 12 × CC-HOOD-NAVY/M from Bulldog
Print Co, $264.00, arrival 2026-09-05, `pending_human_approval`. **Accounting used the 8 units on
hand**, costing the shortfall at $264.00 rather than the original run's $440.00. No duplicates, no
invented discount, no asserted vendor quote; the $104 cross-ticket shortfall was identified again.
Original run preserved unchanged (`6bbc9105…`); rerun archived separately. Nothing approved or
executed; tickets 101 and 102 not re-run._

### Follow-up prompt 5 — final human decisions

> Problem 9: Record and implement my final human decisions.
>
> My explicit decisions are:
>
> * PAY-0002 ($2,400 rent, lease 1): APPROVE ONLY. Do not execute.
> * PAY-0001 ($840 invoice 501): HOLD. Do not approve, reject, or execute.
> * PUR-0001 ($264 estimated purchase of 12 CC-HOOD-NAVY size M): HOLD. Do not approve, reject, or execute.
>
> Work within the existing implementation. Do not add new approval states, modify authorization rules, or rerun any agents.
>
> 1. Verify the three proposal IDs, amounts, targets, and current statuses against the actual proposal ledger. Verify the current cash balance, payment count, inventory, ticket statuses, and original database checksum.
> 2. Use the existing authenticated human-operator approval workflow to approve PAY-0002 ONLY. This instruction is my authorization to record approval, not to execute the payment. Do not access or invoke any execute_payment or execute_purchase operation.
> 3. If the operator approval workflow requires authentication or an interactive step, use the existing documented procedure. Do not bypass authentication, forge an approval signature, or invent an operator identity. If you cannot complete the approval legitimately, stop and tell me exactly what I need to do.
> 4. Leave PAY-0001 and PUR-0001 at their genuine pending_human_approval statuses. Record HOLD as human review decisions in output/results.md, not as fabricated proposal states.
> 5. Independently verify the resulting state:
>    * PAY-0002 is approved with a valid approval record.
>    * PAY-0001 and PUR-0001 remain pending_human_approval.
>    * Checking remains $3,400.00.
>    * Zero payments have executed.
>    * No inventory or ticket-status changes occurred.
>    * The original database is unchanged.
>    * The audit trail retains all previous events and records the genuine approval action.
> 6. Update output/results.md with the human decisions, resulting proposal states, and the distinction between approval and execution. Update output/harness.md and log this actual prompt and any follow-ups in AI_prompts.md.
> 7. Preserve all original and post-fix agent runs, Problem 6 predictions, and prior audit evidence. Do not rewrite historical results or fabricate missing events.
>
> Stop after verification. Do not execute any payments or purchases, process additional tickets, or begin Problem 10.
> Report the exact approval result, audit evidence, and final financial/database state.

_Outcome: **PAY-0002 approved only** via the authenticated operator route (principal
`operator (local)`, signature verifies against the server key and fails against a tampered amount).
**No execution.** PAY-0001 and PUR-0001 left at genuine `pending_human_approval` with holds recorded
as review notes. Balance still $3,400.00, zero payments, all tickets open, both databases unchanged.
Audit 523 → 527, all prior events retained. Also recorded a known wart: the audit trail carries
`execute_*` entries from sandboxed test runs that never touched the real database._

### Follow-up prompt 6 — isolate test audit logs

> Problem 9 final cleanup: isolate test audit logs from the real audit trail.
>
> The real proposal decisions have been implemented:
>
> * PAY-0002: approved, not executed
> * PAY-0001: held, pending_human_approval
> * PUR-0001: held, pending_human_approval
>
> Do not change these decisions or execute any transactions.
>
> A real audit-integrity issue was identified: tests/verify_mcp.py and tests/verify_purchase_permissions.py use disposable databases but write some events to the production audit path.
>
> Make the smallest safe correction:
>
> 1. Inspect the test setup and audit-path configuration to identify exactly why those tests write to the real audit file.
> 2. Redirect all audit output from those tests to isolated temporary paths. Ensure test cleanup cannot affect the real audit trail.
> 3. Add a focused regression check proving that running the affected tests does not modify the production audit file.
> 4. Do not delete, rewrite, or fabricate any historical audit entries. Document the previously identified test-origin execution events transparently in output/harness.md and output/results.md.
> 5. Run the affected tests and verify the fix. Avoid unnecessarily rerunning unrelated live-agent tests.
> 6. Independently verify that PAY-0002 remains approved but unexecuted; PAY-0001 and PUR-0001 remain pending; checking remains $3,400; payments remain zero; inventory and ticket statuses are unchanged.
> 7. Preserve all original predictions, agent runs, proposal evidence, and original database content.
> 8. Record this prompt and any follow-ups in AI_prompts.md.
>
> Stop after verification. Do not rerun tickets, approve or execute additional proposals, or begin Problem 10.
> Report the exact files changed, tests passed, production audit checksum before and after testing, and final database/proposal state.

**One correction to the premise:** measurement showed `verify_purchase_permissions.py` was **not** a
polluter — it already redirected the audit path. The actual culprits were `verify_mcp.py` (+41
entries) plus `verify_pydanticai.py` (+14) and `verify_team.py` (+13), two suites not previously
identified.

_Outcome: new `tests/_isolation.py` redirects audit writes to a temp dir with cleanup scoped to that
dir; the three suites call it before importing `mcp_server` and assert isolation. New
`tests/verify_audit_isolation.py` empirically proves every suite leaves the production log
byte-identical — **8/8 with `--all`**. Historical entries untouched. Also corrected a now-stale
assertion in `verify_purchase_permissions.py` that assumed all proposals were pending, which the
operator's PAY-0002 approval had legitimately invalidated._

---

## Problem 10: Reflection

### Initial prompt

> Problem 10: Write and record my reflection on the Campus Customs multi-agent assignment.
>
> First, read the exact Problem 10 instructions in the assignment and follow its required format, length, and submission location. Do not assume requirements.
>
> Review the existing evidence:
>
> * output/predictions.md
> * output/results.md
> * output/harness.md
> * The original and post-fix ticket run archives
> * Relevant audit records and test results
>
> Write a thoughtful first-person reflection in my voice, using clear, natural language appropriate for an MBA student. Avoid generic AI praise, overly technical jargon, and exaggerated claims.
>
> Address the following, insofar as they match the assignment requirements:
>
> 1. How the Boss and specialist agents performed across Tickets 101, 102, and 103.
> 2. How actual behavior compared with my predictions, especially the two predicted failures that did not occur.
> 3. The strongest example of successful coordination: recognizing that the $840 invoice, $2,400 rent, and estimated $264 restock exceeded $3,400 in cash by $104.
> 4. The purchasing-permission defect revealed by the original Ticket 103 run, why it mattered, and how the corrected rerun demonstrated improvement.
> 5. The audit-isolation problem uncovered during testing and the importance of separating test activity from genuine business records.
> 6. The distinction between generating recommendations, obtaining human approval, and executing actions.
> 7. The limitations that remain, including unverified vendor information, missing discount authorization, and the fact that all three tickets remain open.
>
> Be candid and specific. Clearly distinguish agent reasoning failures from system configuration or testing defects.
> Do not invent experiences, outcomes, vendor confirmations, or ticket resolutions. Do not imply that PAY-0002 was executed: it was approved only, and checking remains $3,400.
> Preserve all existing evidence and predictions unchanged.
> Create the reflection in the assignment's required location. If the assignment does not specify one, use output/reflection.md.
> Update AI_prompts.md with this prompt and any actual follow-ups. Update output/harness.md only if necessary to document the reflection.
> Do not start Problem 11, publish to GitHub, change proposals, or run additional agents.
> Report the reflection's location, word count, and how it meets the exact Problem 10 requirements. Show me the full draft for review before treating it as final.

**Requirements followed:** the seven Problem 10 points recorded in the prompt above, written to
`output/reflection.md`. No mandatory word count applies.

### Follow-up prompt — revision

> Revise my existing Problem 10 reflection in `output/reflection.md`.
>
> There is no separate assignment handout. The assignment instructions were provided as screenshots in our earlier work. Do not search for a PDF or claim that a handout is missing.
>
> Follow the Problem 10 requirements already documented in the project, if available. Do not invent additional requirements or a mandatory word count.
>
> Aim for approximately 900–1,100 words as an editorial recommendation, not an assignment requirement.
>
> Apply the revision feedback provided in my previous prompt, preserving the specific evidence, personal observations, and lessons learned.
>
> Show me the complete revised reflection and word count before treating it as final. Record this follow-up in `AI_prompts.md`. Do not begin Problem 11.

**What was missing:** the first draft ran to ~1,680 words and the project notes framed the Problem
10 requirements as unreadable because no handout file was present; the requirements were in fact
already documented in this log, and the length needed tightening. The revision cuts to ~1,190 words
and removes the missing-handout framing from `output/harness.md` and this entry. Since the previous
prompt contained the seven required topics rather than a separate feedback list, "revision feedback"
was read as: keep all seven, keep the specific evidence, quotations, and personal observations, and
shorten. The result sits slightly above the 900–1,100 editorial target because further cuts would
have removed the quoted agent reasoning the reflection depends on.

### Follow-up prompt — three final corrections

%s

**What was missing:** three claims in the draft were imprecise. Calling $22 a "floor" implied a
pricing policy the shop does not have — it is simply the recorded unit cost, and nothing in the data
says what a sale may go below. The conclusion read as though the system were incapable of resolving
tickets, when in fact it can carry one through to execution once a person authorizes it; these three
tickets went unresolved because each turned on a judgment the data couldn't settle. And the opening
framed the goal as not having to check numbers, which undersells human oversight — the point is that
the agents coordinate and verify facts so a person's judgment is applied to accurate ones.

_Outcome: three edits applied, ~1,350 words, nothing else changed. Quotations re-verified verbatim
against `run_101.json`, `run_103.json`, and `run_103_postfix.json`; the $22/$58 figures re-checked
against the `pricing` table. **Problem 10 complete.**_

---

## Problem 11: Publish to GitHub

### Initial prompt

> Problem 11: Prepare, publish, and verify my completed Campus Customs multi-agent project on GitHub.
>
> This is the final submission step for Yale AI Foundations Homework 5.
> Follow the Problem 11 requirements previously documented in the project. There is no separate assignment handout; the instructions were provided as screenshots.
> Work efficiently. Reuse existing test results and evidence rather than unnecessarily rerunning live agents or making API calls.
>
> 1. Audit submission completeness
> [five-agent team and prompts, FastMCP server and database tools, FastAPI backend, React frontend, both SQLite files, AI_prompts.md, output/harness.md, output/predictions.md, output/results.md, output/reflection.md, archived agent runs and tests, setup instructions and dependency files]
>
> 2. Security and privacy audit
> [API keys, bearer tokens, passwords, credentials, .env, .secrets/, signing keys, operator tokens, hard-coded secrets, personal information; ensure .gitignore excludes them and they are not staged or tracked; do not delete local secrets needed to run]
>
> 3. Final project verification
> [original database unchanged; working database and proposal ledger preserve the final Problem 9 state; PAY-0002 approved but not executed; PAY-0001 and PUR-0001 pending; checking $3,400 and no payments executed; all three tickets open; predictions, run archives and audit history intact; README explains installation, environment configuration, running backend/frontend, how the agents work, and the human approval workflow; README must not claim the tickets were fully resolved]
>
> 4. GitHub publication
> [prepare a clean public repository; use an existing one if configured, otherwise create `campus-customs-multi-agent`; before making public or pushing, show the intended URL and visibility, the file list, security scan results, and any outstanding concerns; stop and request confirmation before publishing]
>
> 5. Post-publication verification
> [verify public accessibility; confirm both database files and all major deliverables present; confirm no secrets committed; record the verified URL in output/github_url.txt; record this Problem 11 prompt and any actual follow-ups]

_(The prompt as sent ended mid-sentence at "Record this Problem 11 prompt and any actual". Read as
"...follow-ups in AI_prompts.md", matching the pattern used throughout. Requirement text above is
abbreviated in brackets where the original enumerated sub-points at length.)_

### Follow-up 1 — verify the README covers local credential initialization

> Before publication, verify that README.md accurately explains how local operator credentials and
> approval signing keys are initialized, and that historical approval signatures may not verify with
> newly generated local keys.
>
> Do not commit any real credentials or signing keys.
>
> If the README already covers this, make no changes.
>
> Then stop and show me the result. Do not publish yet.

**What was missing:** the README said only that the two secrets are "generated automatically on
first use" and omitted the consequence — that `output/proposals.json` is committed with PAY-0002's
HMAC signature, which was produced with a local key that is deliberately not published, so a fresh
clone generating its own key cannot verify it. Confirmed empirically on a simulated clone
(`approval.verify()` returned `False`), then documented: PAY-0002 reads as `approved` but cannot be
executed elsewhere, which is the system correctly failing closed.

### Follow-up 2 — publication authorization

> I explicitly approve publishing my completed Campus Customs Homework 5 project to the following
> GitHub repository:
> Repository: rfr24/campus-customs-multi-agent
> Visibility: PUBLIC
> Proceed with the previously reviewed publication plan.
>
> 1. Perform one final check that no API keys, operator tokens, approval signing keys, `.env` files,
>    or `.secrets/` contents are staged.
> 2. Create the public repository, commit the approved project files, and push them to GitHub.
> 3. Verify that the repository is publicly accessible and that both required SQLite databases, the
>    README, AI_prompts.md, and all assignment deliverables are present.
> 4. Verify that no secrets were published.
> 5. Write the verified GitHub URL to `output/github_url.txt`.
> 6. Record this final publication authorization and the actual GitHub actions in AI_prompts.md.
> 7. Commit and push any final documentation updates so the GitHub repository contains the completed
>    submission records.
> 8. Report the verified public URL, final commit hash, and any remaining submission steps.
>
> Do not execute payments or purchases, change proposal decisions, rerun agents, or alter the
> historical audit evidence.
> Do not claim the assignment has been submitted to Canvas unless that submission actually occurs.

**Actual GitHub actions taken:**

1. `git init`, `git add -A` — 74 files staged after excluding `.secrets/`, `.env`, `.claude/`
   (absolute home paths), build artifacts, and the redundant data archive.
2. Pre-push scan against the three live secrets on this machine — clean.
3. `git commit` — `0a67bf0`.
4. `gh repo create campus-customs-multi-agent --public --source=. --remote=origin`.
5. `git push -u origin main`.
6. Verified public: `gh repo view` reports `PUBLIC`/`isPrivate: false`, and an unauthenticated
   `curl` of the repo page returned HTTP 200.
7. Queried the published git tree via the GitHub API — all 21 checked deliverables present, both
   `.db` files at 53,248 bytes, five agent prompts, seven Python suites, five frontend tests.
8. Cloned the published repo back down and re-scanned its contents against the live secrets —
   clean; both databases hash to `23686a90…`, matching local.
9. Wrote `output/github_url.txt`; committed and pushed final documentation.

No payment or purchase was executed, no proposal decision changed, no agent re-run, and no audit
entry altered.

---
