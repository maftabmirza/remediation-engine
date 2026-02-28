// Atlas Configuration for AIOps Remediation Engine
// Documentation: https://atlasgo.io/atlas-schema/projects

// Define variables for connection strings
variable "database_url" {
  type    = string
  default = getenv("DATABASE_URL")
}

// Development environment - for generating migrations
env "dev" {
  // Dev database for computing migrations
  // Use a temporary database for safe diffing
  dev = "docker://postgres/16/dev?search_path=public"
  
  // Source schema file
  src = "file://schema/schema.sql"
  
  // Migration directory
  migration {
    dir = "file://atlas/migrations"
  }
  
  // Exclude alembic_version if it exists
  exclude = ["alembic_version"]
}

// Production/deployment environment
env "prod" {
  // Target database URL from environment
  url = var.database_url
  
  // Source schema
  src = "file://schema/schema.sql"
  
  // Migration directory
  migration {
    dir    = "file://atlas/migrations"
    format = golang-migrate  // Simple format, easy to read
  }
  
  // Exclude alembic_version table from management
  exclude = ["alembic_version"]
}

// Local development environment
env "local" {
  url = "postgres://aiops:aiops@localhost:5432/aiops?sslmode=disable"
  
  src = "file://schema/schema.sql"
  
  migration {
    dir = "file://atlas/migrations"
  }
  
  dev = "docker://postgres/16/dev?search_path=public"
  
  exclude = ["alembic_version"]
}

// Lint configuration for migration safety
lint {
  // Detect destructive changes
  destructive {
    error = true
  }
  // Require concurrent index creation
  concurrent_index {
    error = true
  }
}
