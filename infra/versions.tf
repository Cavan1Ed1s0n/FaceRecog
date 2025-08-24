terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google      = { source = "hashicorp/google",      version = "~> 5.30" }
    kubernetes  = { source = "hashicorp/kubernetes",  version = "~> 2.33" }
    helm        = { source = "hashicorp/helm",        version = "~> 2.13" }
    null        = { source = "hashicorp/null",        version = "~> 3.2" }
  }
}
