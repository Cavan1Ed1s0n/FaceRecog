# Enable necessary Google APIs
resource "google_project_service" "enabled" {
  for_each = toset([
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
  ])
  service = each.key
}

# Artifact Registry
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = var.repo_name
  format        = "DOCKER"
  description   = "Docker repo for FaceRecog images"
  depends_on    = [google_project_service.enabled]
}

# GKE cluster (no default node pool)
resource "google_container_cluster" "gke" {
  name                     = var.cluster_name
  location                 = var.zone
  remove_default_node_pool = true
  initial_node_count       = 1
  networking_mode          = "VPC_NATIVE"
  depends_on               = [google_project_service.enabled]

  # minimal defaults; adjust to your needs
  ip_allocation_policy {}
}

# CPU node pool
resource "google_container_node_pool" "cpu_pool" {
  name     = "cpu-pool"
  cluster  = google_container_cluster.gke.name
  location = var.zone

  node_config {
    machine_type = "e2-standard-4"
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    labels       = { pool = "cpu" }
  }

  autoscaling { min_node_count = 1 max_node_count = 3 }
}

# Optional GPU pool
resource "google_container_node_pool" "gpu_pool" {
  count    = var.enable_gpu ? 1 : 0
  name     = "gpu-pool"
  cluster  = google_container_cluster.gke.name
  location = var.zone

  node_config {
    machine_type = "n1-standard-8"
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    guest_accelerator {
      type  = "nvidia-tesla-t4"
      count = 1
    }
    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }
  }

  autoscaling { min_node_count = 0 max_node_count = 2 }
  depends_on = [google_container_node_pool.cpu_pool]
}

# Kubernetes namespaces
resource "kubernetes_namespace" "app_ns" {
  metadata { name = var.app_namespace }
}
resource "kubernetes_namespace" "monitoring_ns" {
  metadata { name = "monitoring" }
}
resource "kubernetes_namespace" "observability_ns" {
  metadata { name = "observability" }
}
resource "kubernetes_namespace" "ingress_ns" {
  metadata { name = "ingress-nginx" }
}

# Helm installs
resource "helm_release" "ingress_nginx" {
  name       = "ingress-nginx"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart      = "ingress-nginx"
  namespace  = kubernetes_namespace.ingress_ns.metadata[0].name
  version    = "4.11.2"
  depends_on = [google_container_node_pool.cpu_pool]
}

resource "helm_release" "kps" {
  name       = "kps"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = kubernetes_namespace.monitoring_ns.metadata[0].name

  set { name = "grafana.adminUser"     value = "admin" }
  set { name = "grafana.adminPassword" value = "admin" }

  depends_on = [helm_release.ingress_nginx]
}

resource "helm_release" "loki" {
  name       = "loki"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki-stack"
  namespace  = kubernetes_namespace.monitoring_ns.metadata[0].name

  set { name = "promtail.enabled" value = "true" }

  depends_on = [helm_release.kps]
}

resource "helm_release" "jaeger" {
  name       = "jaeger"
  repository = "https://jaegertracing.github.io/helm-charts"
  chart      = "jaeger"
  namespace  = kubernetes_namespace.observability_ns.metadata[0].name

  set { name = "provisionDataStore.cassandra" value = "false" }
  set { name = "storage.type"                 value = "memory" }

  depends_on = [helm_release.ingress_nginx]
}

resource "helm_release" "dcgm" {
  count      = var.enable_gpu ? 1 : 0
  name       = "dcgm-exporter"
  repository = "https://nvidia.github.io/dcgm-exporter"
  chart      = "dcgm-exporter"
  namespace  = kubernetes_namespace.monitoring_ns.metadata[0].name

  set { name = "daemonset.tolerations[0].key"      value = "nvidia.com/gpu" }
  set { name = "daemonset.tolerations[0].operator" value = "Exists" }
  set { name = "daemonset.tolerations[0].effect"   value = "NoSchedule" }

  depends_on = [google_container_node_pool.gpu_pool, helm_release.kps]
}
