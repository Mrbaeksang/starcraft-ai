package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

const manifestSchema = "scai-remastered-client-v1"

// ClientManifest pins one executable build. No memory bindings are trusted
// unless the process image exactly matches this identity.
type ClientManifest struct {
	Schema         string `json:"schema"`
	Product        string `json:"product"`
	Version        string `json:"version"`
	Architecture   string `json:"architecture"`
	ExecutableName string `json:"executable_name"`
	SHA256         string `json:"sha256"`
}

func loadManifest(path string) (ClientManifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return ClientManifest{}, err
	}
	var manifest ClientManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return ClientManifest{}, err
	}
	if manifest.Schema != manifestSchema || manifest.Product != "starcraft-remastered" ||
		manifest.Version == "" || manifest.Architecture != "x86_64" ||
		manifest.ExecutableName != "StarCraft.exe" {
		return ClientManifest{}, errors.New("unsupported or incomplete client manifest")
	}
	decoded, err := hex.DecodeString(manifest.SHA256)
	if err != nil || len(decoded) != sha256.Size {
		return ClientManifest{}, errors.New("client manifest has invalid sha256")
	}
	return manifest, nil
}

func verifyImage(manifest ClientManifest, imagePath string) (string, error) {
	if !sameExecutableName(filepath.Base(imagePath), manifest.ExecutableName) {
		return "", fmt.Errorf("unexpected client executable: %s", filepath.Base(imagePath))
	}
	file, err := os.Open(imagePath)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hasher := sha256.New()
	if _, err := io.Copy(hasher, file); err != nil {
		return "", err
	}
	observed := hex.EncodeToString(hasher.Sum(nil))
	if observed != manifest.SHA256 {
		return observed, fmt.Errorf("client build mismatch: expected %s, observed %s", manifest.SHA256, observed)
	}
	return observed, nil
}

func sameExecutableName(actual, expected string) bool {
	return strings.EqualFold(actual, expected)
}
