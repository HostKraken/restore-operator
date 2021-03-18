from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import json

class Controller(BaseHTTPRequestHandler):
  def sync(self, parent, children):
    # Compute status based on observed state.
    desired_status = {
      "jobs": len(children["Pod.v1"])
    }

    # Generate the desired child object(s).
    domain = parent.get("spec", {}).get("domain", "invalid.com")
    domain_dashed = domain.replace(".","-")
    restorepoint = parent.get("spec", {}).get("restorepoint", "0000-00-00")
    desired_pods = [
      {

        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
          "name": parent["metadata"]["name"]
        },
        "spec": {
          "containers": [
            {
              "args": [
                "/bin/restore-site %s" % domain
              ],
              "env": [
                {
                  "name": "VAULT_ADDR",
                  "value": "https://vaultino.vault-infra.svc.cluster.local:8200"
                },
                {
                  "name": "VAULT_SKIP_VERIFY",
                  "value": "false"
                },
                {
                  "name": "VAULT_PATH",
                  "value": "kubernetes"
                },
                {
                  "name": "VAULT_ROLE",
                  "value": "default"
                },
                {
                  "name": "VAULT_IGNORE_MISSING_SECRETS",
                  "value": "false"
                },
                {
                  "name": "VAULT_CACERT",
                  "value": "/vault/tls/ca.crt"
                },
                {
                  "name": "DATABASE_HOST",
                  "value": "%s-mysql.wordpress.svc" % domain_dashed
                },
                {
                  "name": "DATABASE_USER",
                  "value": "vault:secret/data/mysql/%s#user" % domain_dashed
                },
                {
                  "name": "DATABASE_NAME",
                  "value": "vault:secret/data/mysql/%s#name" % domain_dashed
                },
                {
                  "name": "DATABASE_PASS",
                  "value": "vault:secret/data/mysql/%s#pass" % domain_dashed
                },
                {
                  "name": "BUCKET",
                  "value": "hostkraken-backup"
                },
                {
                  "name": "AWS_ACCESS_KEY_ID",
                  "value": "vault:secret/data/backup-secret#access_key"
                },
                {
                  "name": "AWS_SECRET_ACCESS_KEY",
                  "value": "vault:secret/data/backup-secret#secret_key"
                },
                {
                  "name": "SITE_NAME",
                  "value": "%s" % domain
                },
                {
                  "name": "RESTOREPOINT",
                  "value": "%s" % restorepoint
                }
              ],
              "image": "registry.digitalocean.com/business-business/restoresite:latest",
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
          "initContainers": [
            {
              "command": [
                "sh",
                "-c",
                "cp /usr/local/bin/vault-env /vault/"
              ],
              "image": "banzaicloud/vault-env:latest",
              "imagePullPolicy": "IfNotPresent",
              "name": "copy-vault-env",
              "resources": {},
              "terminationMessagePath": "/dev/termination-log",
              "terminationMessagePolicy": "File",
              "volumeMounts": [
                {
                  "mountPath": "/vault/",
                  "name": "vault-env"
                }
              ]
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
