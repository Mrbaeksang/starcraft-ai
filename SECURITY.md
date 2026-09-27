# Security policy

## Supported versions

This is an experimental research repository. Security fixes are applied to the current `main` branch.

## Reporting

Do not open a public issue for a vulnerability that could expose local files, execute untrusted code, leak credentials, or compromise a contributor's machine.

Use GitHub's private vulnerability reporting feature when available. If it is unavailable, contact the repository owner privately through the contact information on the owner's GitHub profile.

## Scope

Particular care is required around:

- parsing untrusted replay or dataset files;
- native BWAPI/Windows bridge code;
- subprocess launching;
- path traversal when writing extracted shards;
- model/checkpoint deserialization;
- CI workflows and third-party actions.

Never ask contributors to disable antivirus, Windows security controls, or GitHub security features as a routine setup step.
