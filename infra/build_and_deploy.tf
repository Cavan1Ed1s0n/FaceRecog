# build_and_deploy.tf - clone repo, build/push image, kompose convert, patch manifests, kubectl apply

locals {
  gar_repo_url = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
  image_name   = "face-deepstream-service"
  full_image   = "${local.gar_repo_url}/${local.image_name}:${var.app_image_tag}"
}

# get cluster credentials locally (this runs gcloud -> updates kubeconfig)
resource "null_resource" "get_kubeconfig" {
  provisioner "local-exec" {
    command = <<EOT
      set -euo pipefail
      gcloud container clusters get-credentials ${google_container_cluster.gke.name} --zone ${var.zone} --project ${var.project_id}
    EOT
  }
  depends_on = [google_container_node_pool.cpu_pool]
}

# clone the GitHub repo
resource "null_resource" "clone_repo" {
  provisioner "local-exec" {
    command = <<EOT
      set -euo pipefail
      rm -rf ./app-repo
      git clone "${var.github_repo}" ./app-repo
    EOT
  }
  depends_on = [null_resource.get_kubeconfig]
}

# ensure kompose present (install locally if missing)
resource "null_resource" "ensure_kompose" {
  provisioner "local-exec" {
    command = <<'EOT'
      set -euo pipefail
      if ! command -v kompose >/dev/null 2>&1; then
        echo "installing kompose..."
        curl -L https://github.com/kubernetes/kompose/releases/download/v1.33.0/kompose-linux-amd64 -o kompose
        chmod +x kompose
        sudo mv kompose /usr/local/bin/kompose
      fi
      kompose version
    EOT
  }
  depends_on = [null_resource.clone_repo]
}

# Build & push with gcloud builds (Cloud Build)
resource "null_resource" "cloud_build_submit" {
  provisioner "local-exec" {
    command = <<EOT
      set -euo pipefail
      echo "Building and pushing image to Artifact Registry: ${local.full_image}"
      # Authenticate docker to GAR and submit build via Cloud Build
      gcloud auth configure-docker ${var.region}-docker.pkg.dev --quiet

      # Use gcloud builds submit to build and push from repo root
      gcloud builds submit ./app-repo --tag "${local.full_image}" --project="${var.project_id}"
      echo "${local.full_image}" > .image_pinned.txt
    EOT
  }
  depends_on = [null_resource.ensure_kompose, google_artifact_registry_repository.repo]
}

# convert docker-compose -> k8s manifests (PVCs)
resource "null_resource" "kompose_convert" {
  provisioner "local-exec" {
    command = <<EOT
      set -euo pipefail
      rm -rf ./k8s-manifests
      mkdir -p ./k8s-manifests
      kompose convert -f ./app-repo/docker-compose.yml -o ./k8s-manifests --volumes pvc --namespace ${var.app_namespace}
    EOT
  }
  depends_on = [null_resource.cloud_build_submit]
}

# patch generated manifests to use the Artifact Registry image for the app (face-deepstream-service)
resource "null_resource" "patch_manifests" {
  provisioner "local-exec" {
    command = <<EOT
      set -euo pipefail
      IMG=$(cat .image_pinned.txt)
      # Replace any image line that references 'face-deepstream-service' with our pushed image
      find ./k8s-manifests -type f -name "*.yaml" -print0 | xargs -0 sed -i "s|image:.*face-deepstream-service.*|image: ${IMG}|g" || true
      # For cases Kompose left image empty, try to insert image into deployments with label match
      # (A quick safety: replace common local image names too)
      find ./k8s-manifests -type f -name "*.yaml" -print0 | xargs -0 sed -i "s|image: face-deepstream-service:.*|image: ${IMG}|g" || true
    EOT
  }
  depends_on = [null_resource.kompose_convert]
}

# apply manifests to cluster
resource "null_resource" "kubectl_apply" {
  provisioner "local-exec" {
    command = <<EOT
      set -euo pipefail
      # Ensure namespace exists
      kubectl get ns ${var.app_namespace} >/dev/null 2>&1 || kubectl create namespace ${var.app_namespace}
      kubectl -n ${var.app_namespace} apply -f ./k8s-manifests
    EOT
  }
  depends_on = [null_resource.patch_manifests]
}

# auto-generate simple Ingress pointing to the service created by Kompose
resource "null_resource" "ingress_autogen" {
  provisioner "local-exec" {
    command = <<'EOT'
      set -euo pipefail
      APP_NS=${APP_NS}
      PROJECT=${PROJECT}
      # choose a service name - prefer one containing 'face' else use first
      SVC=$(kubectl -n ${APP_NS} get svc -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep -m1 face || true)
      if [ -z "${SVC}" ]; then
        SVC=$(kubectl -n ${APP_NS} get svc -o jsonpath='{.items[0].metadata.name}')
      fi
      cat > ./k8s-manifests/ingress-autogen.yaml <<YAML
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: face-deepstream-ingress
  namespace: ${APP_NS}
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
spec:
  rules:
  - host: face.${PROJECT}.nip.io
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ${SVC}
            port:
              number: 80
YAML
      kubectl apply -f ./k8s-manifests/ingress-autogen.yaml
    EOT

    environment = {
      APP_NS  = var.app_namespace
      PROJECT = var.project_id
    }
  }

  depends_on = [null_resource.kubectl_apply, helm_release.ingress_nginx]
}
