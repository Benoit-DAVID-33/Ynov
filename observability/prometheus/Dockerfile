# Metrics collection of the subtitle application: Prometheus with its scrape
# configuration built in.
FROM prom/prometheus:v3.5.0

COPY prometheus.yml /etc/prometheus/prometheus.yml

LABEL org.opencontainers.image.title="subtitle-prometheus" \
      org.opencontainers.image.description="Prometheus scraping the services of the subtitle application" \
      com.ynov.subtitle.component="metrics"
