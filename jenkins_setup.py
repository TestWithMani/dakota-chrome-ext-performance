"""
Configure Jenkins for Dakota Chrome Extension Performance (SCM pipeline).

Creates/updates:
  - Credential dakota-portal-creds
  - Pipeline job Dakota-Chrome-Extension-Performance from GitHub SCM

Usage:
  py -3.13 jenkins_setup.py
  py -3.13 jenkins_setup.py --trigger-build
"""

from __future__ import annotations

import argparse
import json
import sys

import requests

JENKINS_URL = "http://110.93.205.18:8080"
JENKINS_USER = "Muhammad_Usman_Arshad"
JENKINS_PASSWORD = "Rolus@Dakota"

GITHUB_REPO = "https://github.com/TestWithMani/dakota-chrome-ext-performance.git"
GITHUB_BRANCH = "main"

JOB_NAME = "Dakota-Chrome-Extension-Performance"
CREDENTIAL_ID = "dakota-portal-creds"
PORTAL_USERNAME = "demo.development@dakota.com.unified"
PORTAL_PASSWORD = "Rolus334"


def session() -> requests.Session:
    s = requests.Session()
    s.auth = (JENKINS_USER, JENKINS_PASSWORD)
    s.headers.update({"User-Agent": "dakota-chrome-ext-performance-setup/1.0"})
    return s


def crumb_headers(s: requests.Session) -> dict[str, str]:
    resp = s.get(f"{JENKINS_URL}/crumbIssuer/api/json", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return {data["crumbRequestField"]: data["crumb"]}


def credential_exists(s: requests.Session, cred_id: str) -> bool:
    resp = s.get(
        f"{JENKINS_URL}/credentials/store/system/domain/_/api/json",
        params={"depth": 1},
        timeout=30,
    )
    resp.raise_for_status()
    return any(c.get("id") == cred_id for c in resp.json().get("credentials", []))


def create_portal_credential(s: requests.Session) -> None:
    if credential_exists(s, CREDENTIAL_ID):
        print(f"[OK] Credential already exists: {CREDENTIAL_ID}")
        return

    cred_json = {
        "": "0",
        "credentials": {
            "scope": "GLOBAL",
            "id": CREDENTIAL_ID,
            "username": PORTAL_USERNAME,
            "password": PORTAL_PASSWORD,
            "description": "Dakota Marketplace portal login for Chrome extension performance tests",
            "$class": "com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl",
        },
    }
    headers = crumb_headers(s)
    resp = s.post(
        f"{JENKINS_URL}/credentials/store/system/domain/_/createCredentials",
        headers=headers,
        data={"json": json.dumps(cred_json)},
        timeout=60,
    )
    if resp.status_code not in (200, 201, 302):
        raise RuntimeError(f"Create credential failed HTTP {resp.status_code}: {resp.text[:1000]}")
    print(f"[OK] Created credential: {CREDENTIAL_ID}")


def job_exists(s: requests.Session, name: str) -> bool:
    return s.get(f"{JENKINS_URL}/job/{name}/api/json", timeout=30).status_code == 200


def build_scm_job_config_xml() -> str:
    return f"""<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>Dakota Chrome Extension performance — Selenium headless, Excel, Allure, email</description>
  <keepDependencies>false</keepDependencies>
  <properties/>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps">
    <scm class="hudson.plugins.git.GitSCM" plugin="git">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>{GITHUB_REPO}</url>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches>
        <hudson.plugins.git.BranchSpec>
          <name>*/{GITHUB_BRANCH}</name>
        </hudson.plugins.git.BranchSpec>
      </branches>
      <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
      <submoduleCfg class="empty-list"/>
      <extensions/>
    </scm>
    <scriptPath>Jenkinsfile</scriptPath>
    <lightweight>false</lightweight>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>
"""


def create_or_update_job(s: requests.Session) -> None:
    config_xml = build_scm_job_config_xml()
    headers = crumb_headers(s)
    headers["Content-Type"] = "application/xml; charset=UTF-8"

    if job_exists(s, JOB_NAME):
        resp = s.post(
            f"{JENKINS_URL}/job/{JOB_NAME}/config.xml",
            headers=headers,
            data=config_xml.encode("utf-8"),
            timeout=120,
        )
        action = "Updated"
    else:
        resp = s.post(
            f"{JENKINS_URL}/createItem",
            params={"name": JOB_NAME},
            headers=headers,
            data=config_xml.encode("utf-8"),
            timeout=120,
        )
        action = "Created"

    if resp.status_code not in (200, 201, 302):
        raise RuntimeError(f"{action} job failed HTTP {resp.status_code}: {resp.text[:1500]}")
    print(f"[OK] {action} SCM pipeline job: {JOB_NAME}")
    print(f"     Repo: {GITHUB_REPO}")
    print(f"     Branch: {GITHUB_BRANCH}")


def trigger_build(s: requests.Session) -> None:
    headers = crumb_headers(s)
    resp = s.post(f"{JENKINS_URL}/job/{JOB_NAME}/build", headers=headers, timeout=30)
    if resp.status_code not in (200, 201, 302):
        raise RuntimeError(f"Trigger build failed HTTP {resp.status_code}: {resp.text[:500]}")
    print(f"[OK] Build triggered: {JENKINS_URL}/job/{JOB_NAME}/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trigger-build", action="store_true")
    args = parser.parse_args()

    s = session()
    print(f"Jenkins: {JENKINS_URL}")
    s.get(f"{JENKINS_URL}/api/json", timeout=30).raise_for_status()
    print("[OK] Jenkins API login successful")

    create_portal_credential(s)
    create_or_update_job(s)

    if args.trigger_build:
        trigger_build(s)

    print(f"\nJob URL: {JENKINS_URL}/job/{JOB_NAME}/")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
