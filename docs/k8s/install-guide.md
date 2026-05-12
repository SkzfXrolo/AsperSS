# Instalacion en Kubernetes

## Kubectl manifests

1. `kubectl apply -f scripts/k8s/manifests/configmap.yml`
2. `kubectl apply -f scripts/k8s/manifests/secret.yml.example` (adaptado)
3. `kubectl apply -f scripts/k8s/manifests/deployment.yml`
4. `kubectl apply -f scripts/k8s/manifests/service.yml`
5. `kubectl apply -f scripts/k8s/manifests/ingress.yml`

## Helm

`helm upgrade --install argus scripts/k8s/helm/argus`
