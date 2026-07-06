terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0, < 8.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  labels = {
    app        = "schema-assistant"
    env        = var.environment
    managed_by = "terraform"
  }
}

module "project_services" {
  source = "../../modules/project_services"

  project_id = var.project_id
  services   = var.enabled_services
}

module "foundation" {
  source = "../../modules/foundation"

  project_id                      = var.project_id
  region                          = var.region
  environment                     = var.environment
  service_prefix                  = var.service_prefix
  labels                          = local.labels
  bucket_name                     = var.bucket_name
  artifact_registry_repository_id = var.artifact_registry_repository_id
  firestore_location              = var.firestore_location
  firestore_deletion_policy       = var.firestore_deletion_policy
  firestore_delete_protection     = var.firestore_delete_protection
  force_destroy_bucket            = var.force_destroy_bucket

  depends_on = [module.project_services]
}

module "cloud_run" {
  source = "../../modules/cloud_run"

  project_id                      = var.project_id
  region                          = var.region
  environment                     = var.environment
  service_prefix                  = var.service_prefix
  labels                          = local.labels
  agent_image                     = var.agent_image
  ingestion_image                 = var.ingestion_image
  agent_service_account_email     = module.foundation.agent_service_account_email
  ingestion_service_account_email = module.foundation.ingestion_service_account_email
  bucket_name                     = module.foundation.bucket_name
  firestore_database_name         = module.foundation.firestore_database_name
  developer_invokers              = var.developer_invokers
  deletion_protection             = var.cloud_run_deletion_protection

  depends_on = [module.foundation]
}
