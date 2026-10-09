The OGCR registry records carbon activities, parcels, verifications and certificates, and turns verified facts into tokens on the OGCR blockchain. A spreadsheet defines the registry's data model and access rules, which are served as secured APIs. The on-chain state is mirrored back into the registry, where it can be filtered and combined with off-chain data.

### Design goals

- **REST API driven.** Every registry operation is a REST call with OpenAPI documentation, and every app and service works through the same APIs.
- **AI enabled.** The Opey Agent and the OBP-MCP server let AI agents read and act on the registry through the same APIs, limited by the same Roles as the user.
- **Agile data model definition and construction.** The data model is defined in a spreadsheet and built as Dynamic Entities at runtime, with their endpoints, Roles and indexes. Changing it needs no code change or redeploy, and existing records are kept.
- **Open source.** OBP-API, the OBP-MCP server, Opey and the OGCR repositories are open source (AGPL-3.0).
- **Open standards.** OAuth2, OpenID Connect, OpenAPI, JSON, MCP, and EVM tokens (ERC-721, ERC-20, ERC-6551).
- **Decoupled apps.** OGCR-App and the Operator and Certifier Platforms are separate apps that depend only on the API, so each can be built, deployed and replaced on its own.
- **OAuth2 / OIDC.** People log in with an OpenID Connect provider, and apps and services call the API with OAuth2 tokens.
- **RBAC.** Each operation on each entity needs a Role, and people get Roles through Role Groups.
- **Dockerised deployment.** Each service is built as a Docker image and deployed on Kubernetes.

### The big picture

```
 Schema definition spreadsheet    OGCR-App, OGCR Operator     Opey Agent, Claude Code
              │                    and Certifier Platforms          |
              v                                |                    v
    OGCR-DynamicEntities                       |               OBP-MCP server
              │ entity definitions, Roles,     |                    |
              │ Role Groups, Dynamic Queries   | CRUD and queries over OAuth2 / OIDC
              v                                v                    v
 +------------------------------------------------------------------+
 │  OBP-API: Dynamic Entities, generated CRUD endpoints,            |
 │  OAuth2 / OIDC, RBAC, indexes, Dynamic Queries (ogcr Space)      |
 +------------------------------------------------------------------+
              ^                                     ^
              │ polls for verified records          | writes *_on_chain records
              │ (reads only)                        |
       ogcr-tokenizer --mints--> OGCR chain <--reads-- OGCR-Chain-Cache
                                (chain id 2025,
                                 OGCR-Smart-Contracts)
```
Arrows point from the caller to the service it calls.

### The components

**OBP-API**: the single gateway to the registry. It stores the Dynamic Entities and generates their CRUD endpoints. Every call is authenticated with OAuth2 / OIDC and checked against Roles (RBAC), such as `CanCreateDynamicEntityRecord_activity`, which people get through Role Groups. Indexes and Dynamic Queries serve filtered and joined views, such as the public registry.

**OGCR-DynamicEntities**: scripts that apply the schema definition spreadsheet to OBP-API. They create the entities (fields, types, references, indexes), the Role Groups and the Dynamic Queries, and check that OBP matches the spreadsheet.

**OGCR-Smart-Contracts**: Solidity contracts for chain 2025. `ParcelNFT`, `ActivityNFT` and `CertificationNFT` hold a URL and hash of the registry record they attest to. Each `CarbonCreditBatchNFT` owns an ERC-6551 account holding its `CarbonCredit` (ERC-20) balance.

**ogcr-tokenizer**: polls OBP and mints a token to the operator's wallet when a record reaches a qualifying state (table below). Each token is minted exactly once, and a token waits until the tokens it depends on exist. It only reads from OBP and reports its health at `/healthz`.

**OGCR-Chain-Cache**: reads every OGCR token from the chain and writes one mirror record per token (`parcel_on_chain`, `activity_on_chain`, ...) into OBP, so on-chain state can be joined with off-chain records through the normal APIs. It owns the definitions of these entities and writes `chain_sync_status` after each run.

**OGCR-App**: the registry's public-facing pages and the marketplace (work in progress). Users log in with OIDC, and it reads and writes through OBP-API, never directly on chain.

**OGCR Operator Platform**: the application for operators, who run the carbon activities.

**OGCR Certifier Platform**: the application for certification bodies, who verify and certify activities.

**OBP-MCP server**: a Model Context Protocol server that lets AI agents discover and call OBP-API endpoints, including the endpoints generated for the registry's Dynamic Entities, and read the Glossary. Claude Code, Claude Desktop and IDE agents connect to it with the user's OAuth token; Opey connects with a Consent-JWT.

**Opey Agent**: OBP's AI assistant, available in the Portal and API Explorer. It calls OBP-API through the OBP-MCP server with a consent the user approves, so it can see and do only what that user's Roles allow. It can answer questions about the registry and help write App Studio pages.

### What the tokenizer mints, and when

| Token | Minted when | Also required |
|---|---|---|
| `ParcelNFT` | `parcel_owner_verification` is `verified` | parcel, activity_parcel_verification, activity, operator |
| `ActivityNFT` | `activity_verification` is `verified` | activity, operator |
| `CertificationNFT` | a `certificate_of_compliance` is created | ActivityNFT, activity, operator |
| `CarbonCreditBatchNFT` + `CarbonCredit` | `activity_monitoring_period_verification` is `verified` | ActivityNFT, certificate_of_compliance, certification_scheme, certification_body |

### Design rules

- **One gateway.** All access to registry data goes through OBP-API, AI agents included, so authentication and Roles are enforced in one place.
- **One-way services.** The tokenizer reads OBP and writes to the chain. The chain cache reads the chain and writes to OBP.
- **Safe to repeat.** Minting is deduplicated on chain and mirror records are upserted, so a rerun never creates duplicates.

### Source code

- [OBP-API](https://github.com/OpenBankProject/OBP-API)
- [OGCR-DynamicEntities](https://github.com/OpenBankProject/OGCR-DynamicEntities)
- [OGCR-Smart-Contracts](https://github.com/OpenBankProject/OGCR-Smart-Contracts)
- [ogcr-tokenizer](https://github.com/TESOBE/ogcr-tokenizer)
- [OGCR-Chain-Cache](https://github.com/TESOBE/OGCR-chain-cache)
- [OGCR-App](https://github.com/OpenBankProject/OGCR-App)
- [OBP-MCP server](https://github.com/OpenBankProject/OBP-MCP)
- [Opey Agent](https://github.com/OpenBankProject/OBP-Opey-II)
- [OBP Portal and API Manager](https://github.com/OpenBankProject/OBP-Frontend)
- [API Explorer II](https://github.com/OpenBankProject/API-Explorer-II)

To browse the registry's endpoints, open [API Explorer II](https://apiexplorer.dcr.ogcr.tesobe.com/?content=dynamic&bank_id=ogcr).
