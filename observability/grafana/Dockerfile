# Dashboards of the subtitle application: Grafana with its Prometheus data source and the
# dashboard built in (outside /var/lib/grafana, which is a volume).
FROM grafana/grafana:12.1.1

COPY provisioning /etc/grafana/provisioning
COPY dashboards /etc/grafana/dashboards
ENV GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=/etc/grafana/dashboards/subtitle-app.json

LABEL org.opencontainers.image.title="subtitle-grafana" \
      org.opencontainers.image.description="Grafana with the dashboard of the subtitle application" \
      com.ynov.subtitle.component="dashboards"
