    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    import json

    class Controller(BaseHTTPRequestHandler):
      def sync(self, parent, children):
        # Compute status based on observed state.
        desired_status = {
          "jobs": 1
        }

        # Generate the desired child object(s).
        domain = parent.get("spec", {}).get("domain", "invalid.com")
        domain_dashed = domain.replace(".","-")
        restorepoint = parent.get("spec", {}).get("restorepoint", "0000-00-00")
        desired_pods = [
          {

            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
              "name": parent["metadata"]["name"]
            },
            "spec": {
            "template": {
             "spec": {
              "containers": [
                {
                  "args": [
                    "/bin/restore-site %s" % domain
                  ],
                  "env": [
                    {
                      "name": "DATABASE_HOST",
                      "value": "%s-mysql.wordpress.svc" % domain_dashed
                    },
                    {
                      "name": "DATABASE_USER",
                      "valueFrom": {
                          "secretKeyRef": {
                              "name": "%s-db-creds-secret" % domain_dashed,
                              "key": "user"
                            }
                        }
                    },
                    {
                      "name": "DATABASE_NAME",
                      "valueFrom": {
                          "secretKeyRef": {
                              "name": "%s-db-creds-secret" % domain_dashed,
                              "key": "name"
                            }
                        }
                    },
                    {
                      "name": "DATABASE_PASS",
                      "valueFrom": {
                          "secretKeyRef": {
                              "name": "%s-db-creds-secret" % domain_dashed,
                              "key": "pass"
                            }
                        }
                    },
                    {
                      "name": "BUCKET",
                      "value": "hostkraken-backup"
                    },
                    {
                      "name": "AWS_ACCESS_KEY_ID",
                      "valueFrom": {
                          "secretKeyRef": {
                              "name": "backup-secret",
                              "key": "access_key"
                            }
                        }
                    },
                    {
                      "name": "AWS_SECRET_ACCESS_KEY",
                      "valueFrom": {
                          "secretKeyRef": {
                              "name": "backup-secret",
                              "key": "secret_key"
                            }
                        }
                    },
                    {
                      "name": "SITE_NAME",
                      "value": "%s" % domain
                    },
                    {
                      "name": "RESTOREPOINT",
                      "value": "%s" % restorepoint
                    },
                    {
                      "name": "JOB_TO_DELETE",
                      "value": parent["metadata"]["name"]
                    },
                    { "name": "KUBE_TOKEN",
                      "valueFrom": {
                          "secretKeyRef": {
                              "name": "default-token-cftxg",
                              "key": "token"
                            }
                        }
                    }
                  ],
                  "image": "registry.hostkraken.com/restoresite:latest",
                  "imagePullPolicy": "Always",
                  "name": "%s-restorebackup" % domain_dashed,
                  "resources": {},
                  "securityContext": {},
                  "terminationMessagePath": "/dev/termination-log",
                  "terminationMessagePolicy": "File",
                  "volumeMounts": [
                    {
                      "mountPath": "/configs",
                      "name": "config-volume"
                    },
                    {
                      "mountPath": "/content",
                      "name": "wp-uploads-%s" % domain_dashed
                    },
                    {
                      "mountPath": "/vault/",
                      "name": "vault-env"
                    },
                    {
                      "mountPath": "/vault/tls/ca.crt",
                      "name": "vault-tls",
                      "subPath": "ca.crt"
                    }
                  ]
                }
              ],
              "dnsPolicy": "ClusterFirst",
              "imagePullSecrets": [
                {
                  "name": "registry-business-business"
                }
              ],
              "restartPolicy": "Never",
              "schedulerName": "default-scheduler",
              "securityContext": {},
              "serviceAccount": "%s" % domain_dashed,
              "serviceAccountName": "%s" % domain_dashed,
              "terminationGracePeriodSeconds": 30,
              "volumes": [
                {
                  "configMap": {
                    "defaultMode": 420,
                    "name": "%s-configmap" % domain_dashed
                  },
                  "name": "config-volume"
                },
                {
                  "name": "wp-uploads-%s" % domain_dashed,
                  "persistentVolumeClaim": {
                    "claimName": "wp-uploads-%s" % domain_dashed
                  }
                },
                {
                  "emptyDir": {
                    "medium": "Memory"
                  },
                  "name": "vault-env"
                },
                {
                  "name": "vault-tls",
                  "secret": {
                    "defaultMode": 420,
                    "secretName": "vault-tls"
                  }
                }
              ]
              }
            }
    }
          }
        ]
        return {"status": desired_status, "children": desired_pods}

      def do_POST(self):
        # Serve the sync() function as a JSON webhook.
        observed = json.loads(self.rfile.read(int(self.headers.getheader("content-length"))))
        desired = self.sync(observed["parent"], observed["children"])
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(desired))

    HTTPServer(("", 80), Controller).serve_forever()
