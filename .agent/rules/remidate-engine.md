---
trigger: always_on
---

Local development environment 

We can test code local and deploy container on laptop, docker desktop is already installed
1. local code PS D:\remediate-engine-antigravity\remediation-engine>
2. Local laptop  container docker remediation-engine


Important : We need to change code on local lapotop first, test , push to git and connect to 172.234.217.11 and pull, docker compose/restart and test


We have 5 ponit of LLM interaction 

1. RE-VIVE - is AI helper for application 
2. RE-VIVE -  on Grafana stack, help user and call Grafana MCP
3. /ai troubeshooting - Need to me manage and develop independed 
4. /ai Inquiry - Read data and answer user question 
5  /alerts help and troubehoot as /ai trouebshooting with some additionl detail


Coding standard

1. Any file which is dedicated to RE-VIVE should have file name with prefix revive
2. Always review impact whcih modifying file , it can impacte other LLM interaction 