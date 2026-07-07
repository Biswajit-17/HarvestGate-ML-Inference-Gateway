FROM grafana/alloy:latest

# Copy config into standard Alloy directory
COPY config.alloy /etc/alloy/config.alloy

# Override entrypoint/CMD to run the configuration with public-preview enabled
ENTRYPOINT ["/usr/bin/alloy"]
CMD ["run", "--stability.level=public-preview", "/etc/alloy/config.alloy"]
