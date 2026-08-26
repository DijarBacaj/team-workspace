# Database Model

```mermaid
erDiagram
    USER ||--o{ REFRESH_TOKEN : owns
    USER ||--o{ MEMBERSHIP : joins
    ORGANIZATION ||--o{ MEMBERSHIP : contains
    USER ||--o{ ORGANIZATION : creates
    ORGANIZATION ||--o{ PROJECT : owns
    ORGANIZATION ||--o{ LABEL : defines
    USER ||--o{ PROJECT : creates
    PROJECT ||--o{ TASK : contains
    USER ||--o{ TASK : creates
    TASK ||--o{ TASK_ASSIGNEE : has
    USER ||--o{ TASK_ASSIGNEE : receives
    TASK ||--o{ TASK_LABEL : has
    LABEL ||--o{ TASK_LABEL : tags
    TASK ||--o{ COMMENT : receives
    USER ||--o{ COMMENT : authors

    USER {
        uuid id PK
        string email UK
        string password_hash
        boolean is_active
    }
    ORGANIZATION {
        uuid id PK
        string slug UK
        uuid created_by_id FK
    }
    MEMBERSHIP {
        uuid organization_id PK,FK
        uuid user_id PK,FK
        enum role
    }
    PROJECT {
        uuid id PK
        uuid organization_id FK
        enum status
    }
    TASK {
        uuid id PK
        uuid project_id FK
        enum status
        enum priority
        datetime due_at
    }
    LABEL {
        uuid id PK
        uuid organization_id FK
        string color
    }
    COMMENT {
        uuid id PK
        uuid task_id FK
        uuid author_id FK
        text body
    }
```

## Important Constraints

- Emails and organization slugs are globally unique.
- Project names and label names are unique inside an organization.
- Memberships, assignments, and task-label links use composite primary keys.
- Foreign keys use cascading deletes only for true ownership relationships.
- Role, status, and priority values have database check constraints.
- The application protects the last organization owner as a transactional rule.

## Important Indexes

- User email and refresh-token JTI for authentication lookups
- Membership user/organization for tenant access
- Project organization/status for project lists
- Task project/status/priority for common dashboard filters
- Task assignee user/task for personal work queues
- Comment task/created timestamp for chronological pagination
