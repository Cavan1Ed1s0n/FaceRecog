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
DeepStream limitation: Designed for continuous video streams, not single-image inference. Pipeline initialization and warmup are slow, and once the stream ends, the pipeline shuts down.
Pipeline constraints: Asynchronous operations (e.g., PostgreSQL queries) should be avoided inside the DeepStream flow, as they may disrupt the continuous pipeline.

## System Architecture

The architecture combines DeepStream-based video inference with cloud-native infrastructure and observability tooling:
+ AI Service: Face detection, registration, search, recognition
+ GPU-Optimized Pipeline: DeepStream + RetinaFace + InsightFace with face alignment plugin
+ Backend & Database: FastAPI + PostgreSQL + pgvector + SQLAlchemy
+ Cloud Deployment: Terraform + GKE (with GPU nodes)
+ Observability: Prometheus + Grafana + Loki + Promtail + Jaeger + OpenTelemetry

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
