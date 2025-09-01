variable "region" {
  type    = string
  default = "ap-southeast-2"
}

variable "stage_name" {
  type    = string
  default = "prod"
}

# S3 front bucket domain (example from CF template)
variable "frontend_s3_domain" {
  type    = string
  default = "qts-front.s3.amazonaws.com"
}

variable "bucket_name" {
  type    = string
  default = "qts-front"
}

variable "argo_namespace" {
  type        = string
  description = "Namespace where ArgoCD Application lives"
  default     = "argocd"
}

variable "argo_app_name" {
  type        = string
  description = "Name of the ArgoCD Application to trigger"
  default     = "trade-app"
}