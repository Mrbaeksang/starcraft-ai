package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func fixture(t *testing.T) (string, string) {
	t.Helper()
	dir := t.TempDir()
	imagePath := filepath.Join(dir, "StarCraft.exe")
	image := []byte("test-only executable contents")
	if err := os.WriteFile(imagePath, image, 0o600); err != nil {
		t.Fatal(err)
	}
	hash := sha256.Sum256(image)
	manifest := ClientManifest{
		Schema: manifestSchema, Product: "starcraft-remastered",
		Version: "1.23.10.13515", Architecture: "x86_64",
		ExecutableName: "StarCraft.exe", SHA256: hex.EncodeToString(hash[:]),
	}
	manifestPath := filepath.Join(dir, "manifest.json")
	data, err := json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(manifestPath, data, 0o600); err != nil {
		t.Fatal(err)
	}
	return manifestPath, imagePath
}

func TestVersionLockedImage(t *testing.T) {
	manifestPath, imagePath := fixture(t)
	manifest, err := loadManifest(manifestPath)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := verifyImage(manifest, imagePath); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(imagePath, []byte("changed build"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := verifyImage(manifest, imagePath); err == nil || !strings.Contains(err.Error(), "mismatch") {
		t.Fatalf("expected build mismatch, got %v", err)
	}
}

func TestManifestRejectsUnsupportedSchema(t *testing.T) {
	manifestPath, _ := fixture(t)
	data, err := os.ReadFile(manifestPath)
	if err != nil {
		t.Fatal(err)
	}
	var manifest ClientManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		t.Fatal(err)
	}
	manifest.Schema = "unverified"
	data, err = json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(manifestPath, data, 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := loadManifest(manifestPath); err == nil {
		t.Fatal("unsupported manifest passed")
	}
}
