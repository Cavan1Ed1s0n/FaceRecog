# Face Recognition System with NVIDIA DeepStream
## Overview

This project demonstrates a Face Recognition system built on NVIDIA DeepStream SDK, optimized to run on NVIDIA hardware (dGPU or Jetson iGPU). By leveraging the GStreamer-based DeepStream framework, the system achieves high-performance face detection and recognition in video streams.

The pipeline integrates RetinaFace for face detection and InsightFace models for feature extraction. A unique customization is implemented: a C++ plugin inside the DeepStream pipeline that performs face alignment before passing images to InsightFace, ensuring robustness and accuracy.

The system provides Face Registration, Face Search, and Face Recognition APIs, backed by a FastAPI service and a PostgreSQL database with pgvector for similarity search.

To support production environments, the project also includes:
+ Infrastructure as Code (IaC) with Terraform for automated deployment on Google Kubernetes Engine (GKE)
+ Observability stack for monitoring performance, logs, and tracing
+ End-to-end reproducibility with Docker and Kubernetes

⚠️ Note: This system relies on GPU hardware. Running on Google Cloud Platform (GCP) requires a billing-enabled account with GPU-enabled instances.
## Limitations
### DeepStream limitation:
The framework is optimized for continuous video streams rather than single-image inference. As a result, pipeline initialization and warmup take time, and once the video stream ends, the pipeline shuts down instead of keeping the model instance alive.
### NVIDIA hardware dependency:
The system relies on the NVIDIA DeepStream SDK, which is only supported on NVIDIA hardware (dGPU or Jetson iGPU). It cannot be natively deployed on CPU-only machines or non-NVIDIA hardware :)
### Pipeline execution flow:
The DeepStream pipeline expects a synchronous, uninterrupted data flow. Introducing asynchronous calls (e.g., PostgreSQL queries or external API calls with async/await) inside the pipeline can break the flow and lead to unexpected behavior or crashes. It’s strongly recommended to keep all operations within the pipeline synchronous and lightweight.
### Lack of built-in CI/CD workflows:
This repository does not currently include any CI/CD automation (e.g., GitHub Actions, Jenkins pipelines, or GitLab CI). You can extend it by adding GitHub Actions, GitLab CI, or Jenkins pipelines to cover automated testing, container builds, and deployment.
## System Architecture

The architecture combines DeepStream-based video inference with cloud-native infrastructure and observability tooling:
+ AI Service: Face detection, registration, search, recognition
+ GPU-Optimized Pipeline: DeepStream + RetinaFace + InsightFace with face alignment plugin
+ Backend & Database: FastAPI + PostgreSQL + pgvector + SQLAlchemy
+ Cloud Deployment: Terraform + GKE (with GPU nodes)
+ Observability: Prometheus + Grafana + Loki + Promtail + Jaeger + OpenTelemetry
![System Architecture](assets/images/System-Architecture-Face-DS.svg)

## Features
### Core Components
+ DeepStream Pipeline: GPU-accelerated video inference, custom C++ postprocessing for face alignment
+ AI Service: FastAPI backend for handling requests (register, search, recognize, video inference)
+ Database Layer: PostgreSQL + pgvector + SQLAlchemy for vector storage and similarity search

### Observability Stack

+ Metrics Monitoring: Prometheus + cAdvisor for real-time hardware and performance tracking

+ Visualization: Grafana dashboards (system metrics, GPU usage, container stats)

+ Log Management: Loki + Promtail for centralized logging

+ Tracing: Jaeger + OpenTelemetry for request tracing and performance analysis

### Cloud Infrastructure

+ Terraform: Automated GCP infrastructure provisioning

+ Kubernetes Orchestration: Scalable GPU deployment on Google Kubernetes Engine (GKE)

+ Docker Compose: Local deployment for AI service and observability stack

## Repository Structure
```bash
├── engine/                        # Face recognition models (.onnx, .trt, .engine, parser configs)
├── gst-nvinfer-custom/            # Custom DeepStream plugin (C++ postprocessing: face alignment)
├── infra/                         # Terraform configs for GCP infrastructure
├── observability/                 # Monitoring and observability stack
├── retinaface/                    # RetinaFace build and runtime files
├── docker-compose.yml             # Start AI service (FastAPI + DB + DeepStream)
├── docker-compose.monitor.yml     # Start observability stack
├── ds_pipeline.py                 # DeepStream pipeline for image & video inference
├── main.py                        # FastAPI service entrypoint
├── schemas.py                     # API response schemas
└── search.py                      # Face search logic with pgvector
```

## Prerequisites
### Hardware & OS

+ Linux / Ubuntu

+ NVIDIA GPU (dGPU or Jetson with CUDA support)

### Required Tools

+ Docker

+ NVIDIA Drivers & CUDA Toolkit

### Optional (for Cloud Deployment)

+ Google Cloud Platform account (GPU-enabled, billing required)

+ Google Cloud SDK

+ Terraform

+ kubectl

+ Helm

## Setup & Usage
### 1. Run AI Service Locally
```bash
docker-compose up -d
```
Access the API at: http://localhost:8090/docs

Try `register` to add a new face

Try `search` to find a face in the database

Try `infer-video` to run face recognition on a video
### 2. Run Observability Service
```bash
docker-compose -f docker-compose.monitor.yml up -d
```
+ Tracing: Open http://localhost:16686 (select face-deepstream-service)

+ Monitoring: Open http://localhost:3000 (login: admin/admin)

#### Grafana Setup

+ Add Data Sources:

Loki → http://loki:3100

Prometheus → http://prometheus:9090

+ Import Dashboards:

Logs: 13639, 14055

System Metrics: 1860, 193

GPU Metrics: 893


## Set up Infrastructure Optional
### infra/ — Terraform + Kompose automation for FaceRecog

`infra/` directory automates:

- GKE cluster provisioning
- Artifact Registry repository creation
- Helm installs: ingress-nginx, kube-prometheus-stack, loki-stack, jaeger, (dcgm-exporter if GPU)
- Clone GitHub repo
- Build & push the app image to Artifact Registry (via `gcloud builds submit`)
- Convert your `docker-compose.yml` into k8s manifests using Kompose
- Patch manifests to point to the pushed image
- Apply manifests to the cluster (kubectl)
- Create a simple Ingress `face.<PROJECT_ID>.nip.io`

#### 1. Gcloud SDK installed and authenticated:
```bash
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT_ID
```
Create service account:
Update configuration in `infra/terraform.tfvars`
```
project_id    = "mythic-inn-466302-j3"  # replace with your gloud project_id
region        = "us-central1"           # replace with your gcloud region
zone          = "us-central1-f"
```
Enable Kubernetes Engine API
```https://console.cloud.google.com/marketplace/product/google/container.googleapis.com```


 Gcloud configured project and grant permission to create GKE clusters, Artifact Registry, Cloud Build, IAM changes. The account must have adequate permissions.
 + kubectl installed ```apt-get install -y kubectl```

#### 2. Run
Initialize Terraform:
```bash
cd infra
terraform init
terraform apply -auto-approve
```

Terraform will:

+ create Artifact Registry and GKE resources

+ install Helm charts

+ clone GitHub repo

+ run gcloud builds submit (build & push your image)

+ run kompose convert and deploy the generated manifests

+ create an Ingress available at: http://face.<PROJECT_ID>.nip.io once the LB IP is allocated

Notes:
+ Cloud Build IAM: gcloud builds submit uses Cloud Build service account (PROJECT_NUMBER@cloudbuild.gserviceaccount.com). Ensure this service account has roles/artifactregistry.writer for the Artifact Registry repo. If push fails, grant that role in IAM.

+ The face search functionality uses pgvector, which performs similarity search based on 'distance' metric between facial feature embeddings. Smaller distance (closer to 0) means the two faces are more similar.
+ The optimal threshold to match face embeddings can vary depending on the model used for feature extraction.
