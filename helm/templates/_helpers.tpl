{{/*
Expand the name of the chart.
*/}}
{{- define "trade.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "trade.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "trade.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "trade.labels" -}}
helm.sh/chart: {{ include "trade.chart" . }}
{{ include "trade.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "trade.selectorLabels" -}}
app.kubernetes.io/name: {{ include "trade.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "trade.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "trade.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Common image pull policy
*/}}
{{- define "trade.imagePullPolicy" -}}
{{- if .Values.global.imageRegistry }}
{{- printf "%s/%s:%s" .Values.global.imageRegistry .repository .tag }}
{{- else }}
{{- printf "%s:%s" .repository .tag }}
{{- end }}
{{- end }}

{{/*
Storage class
*/}}
{{- define "trade.storageClass" -}}
{{- if .Values.global.storageClass }}
{{- .Values.global.storageClass }}
{{- else if .storageClass }}
{{- .storageClass }}
{{- end }}
{{- end }}

{{/*
RabbitMQ connection URL
*/}}
{{- define "trade.rabbitmqUrl" -}}
{{- printf "amqp://admin:password@%s-rabbitmq:5672/" (include "trade.fullname" .) }}
{{- end }}

{{/*
Weaviate connection URL
*/}}
{{- define "trade.weaviateUrl" -}}
{{- printf "http://%s-weaviate:8080" (include "trade.fullname" .) }}
{{- end }}

{{- define "trade.rabbitmqHost" -}}
{{- printf "%s-rabbitmq" (include "trade.fullname" .) }}
{{- end }}

{{/* 
Return the Selenium Hub URL based on values.yaml
*/}}
{{- define "trade.seleniumHubURL" -}}
http://{{ include "trade.fullname" . }}-{{ .Values.selenium.hub.serviceName }}:{{ .Values.selenium.hub.service.port }}/wd/hub
{{- end -}}

{{- define "trade.awsGatewayEndpoint" -}}
 {{(include "trade.fullname" . )}}-aws-gateway:{{ .Values.coreServices.awsGateway.service.port }}
{{- end }}
