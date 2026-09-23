#!/usr/bin/env bash
set -euo pipefail

OWNER="elenaalmansacampos"
REPO="project-py-taximetro"
PROJECT_NUMBER="1"

tasks=(
  "US-01|Iniciar una carrera desde CLI|Fase 1 - MVP Funcional|Must"
  "US-02|Cambiar estado entre parado y movimiento|Fase 1 - MVP Funcional|Must"
  "US-03|Finalizar carrera y mostrar total|Fase 1 - MVP Funcional|Must"
  "US-04|Encadenar varias carreras sin cerrar el programa|Fase 1 - MVP Funcional|Must"
  "US-05|Guardar y consultar historico de carreras|Fase 2 - Observabilidad y Persistencia|Should"
  "US-06|Registrar logs de operacion y errores|Fase 2 - Observabilidad y Persistencia|Should"
  "US-07|Cargar tarifas desde fichero de configuracion|Fase 2 - Observabilidad y Persistencia|Should"
  "US-08|Proteger acceso con contraseña segura|Fase 3 - Arquitectura y UX|Could"
  "US-09|Crear interfaz grafica con botones grandes|Fase 3 - Arquitectura y UX|Could"
  "PROD-01|Migrar historico a base de datos|Fase 4 - Produccion|Won't for MVP"
  "PROD-02|Exponer API REST|Fase 4 - Produccion|Won't for MVP"
  "PROD-03|Crear panel web de historico|Fase 4 - Produccion|Won't for MVP"
  "PROD-04|Preparar despliegue con un comando|Fase 4 - Produccion|Won't for MVP"
)

require_auth() {
  if ! gh auth status >/dev/null 2>&1; then
    echo "GitHub CLI no esta autenticado."
    echo "Ejecuta: gh auth login --hostname github.com --git-protocol https --web"
    exit 1
  fi
}

ensure_project_scope() {
  if ! gh project view "$PROJECT_NUMBER" --owner "$OWNER" >/dev/null 2>&1; then
    echo "No puedo acceder al Project $PROJECT_NUMBER."
    echo "Si falta permiso, ejecuta: gh auth refresh -h github.com -s project"
    exit 1
  fi
}

ensure_label() {
  local label="$1"
  local color="$2"

  gh label create "$label" \
    --repo "$OWNER/$REPO" \
    --color "$color" \
    --force >/dev/null
}

ensure_labels() {
  ensure_label "taximetro" "0366d6"
  ensure_label "Must" "d73a4a"
  ensure_label "Should" "fbca04"
  ensure_label "Could" "0e8a16"
  ensure_label "Won't for MVP" "6a737d"
  ensure_label "Fase 1 - MVP Funcional" "1d76db"
  ensure_label "Fase 2 - Observabilidad y Persistencia" "5319e7"
  ensure_label "Fase 3 - Arquitectura y UX" "c2e0c6"
  ensure_label "Fase 4 - Produccion" "bfdadc"
}

field_exists() {
  local field_name="$1"
  gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json \
    --jq ".fields[].name" | grep -Fxq "$field_name"
}

set_field_if_exists() {
  local issue_url="$1"
  local field_name="$2"
  local value="$3"

  if field_exists "$field_name"; then
    gh project item-edit "$PROJECT_NUMBER" \
      --owner "$OWNER" \
      --url "$issue_url" \
      --field "$field_name" \
      --value "$value" >/dev/null || true
  fi
}

existing_issue_url() {
  local code="$1"
  gh issue list \
    --repo "$OWNER/$REPO" \
    --state all \
    --search "$code in:title" \
    --json title,url \
    --jq ".[] | select(.title | startswith(\"[$code]\")) | .url" \
    | head -n 1
}

create_issue() {
  local code="$1"
  local title="$2"
  local phase="$3"
  local priority="$4"
  local full_title="[$code] $title"
  local issue_url

  issue_url="$(existing_issue_url "$code")"
  if [[ -n "$issue_url" ]]; then
    echo "Existe: $full_title"
    echo "$issue_url"
    return
  fi

  gh issue create \
    --repo "$OWNER/$REPO" \
    --title "$full_title" \
    --body "## Historia / tarea

$title

## Fase

$phase

## Prioridad

$priority

## Fuente

Creada desde docs/github-project-tasks.md" \
    --label "taximetro" \
    --label "$priority" \
    --label "$phase"
}

main() {
  require_auth
  ensure_project_scope
  ensure_labels

  echo "Sincronizando tareas con GitHub Projects..."
  for task in "${tasks[@]}"; do
    IFS="|" read -r code title phase priority <<< "$task"
    issue_url="$(create_issue "$code" "$title" "$phase" "$priority" | tail -n 1)"
    echo "Añadiendo al Project: [$code] $title"
    gh project item-add "$PROJECT_NUMBER" --owner "$OWNER" --url "$issue_url" >/dev/null || true
    set_field_if_exists "$issue_url" "Status" "Backlog"
    set_field_if_exists "$issue_url" "Fase" "$phase"
    set_field_if_exists "$issue_url" "Priority" "$priority"
  done

  echo "Tareas sincronizadas."
}

main "$@"
