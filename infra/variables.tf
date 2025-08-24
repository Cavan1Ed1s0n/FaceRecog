variable "project_id" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "GCP region for Artifact Registry"
  type        = string
  default     = "asia-southeast1"
}

variable "zone" {
  description = "GCP zone for GKE"
  type        = string
  default     = "asia-southeast1-b"
}

variable "cluster_name" {
  description = "GKE cluster name"
  type        = string
  default     = "face-deepstream-gke"
}

variable "repo_name" {
  description = "Artifact Registry repository id"
  type        = string
  default     = "face-repo"
}

# GitHub repo to clone (your public repo)
variable "github_repo" {
  type        = string
  description = "GitHub repo URL to clone"
  default     = "https://github.com/Cavan1Ed1s0n/FaceRecog.git"
}

# Docker image tag to build/push
variable "app_image_tag" {
  type        = string
  default     = "0.0.1"
  description = "Tag to use for face-deepstream-service image"
}

# Namespace where the app will be deployed
variable "app_namespace" {
  type    = string
  default = "model-serving"
}

variable "enable_gpu" {
  description = "Set true to create a GPU node pool and install DCGM exporter"
  type        = bool
  default     = false
}
