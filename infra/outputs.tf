output "artifact_registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

output "gke_cluster_name" {
  value = google_container_cluster.gke.name
}

output "ingress_host_example" {
  value = "http://face.${var.project_id}.nip.io"
}

output "grafana_login" {
  value = "http://<grafana>: use kubectl -n monitoring port-forward svc/kps-grafana 3000:80 (admin/admin)"
}
