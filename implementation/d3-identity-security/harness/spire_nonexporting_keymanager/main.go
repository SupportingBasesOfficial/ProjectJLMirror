package main

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"fmt"
	"os"
	"sort"
	"sync"

	"github.com/spiffe/spire-plugin-sdk/pluginmain"
	keymanagerv1 "github.com/spiffe/spire-plugin-sdk/proto/spire/plugin/agent/keymanager/v1"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type keyRecord struct {
	key       *ecdsa.PrivateKey
	publicKey *keymanagerv1.PublicKey
}

type plugin struct {
	keymanagerv1.UnimplementedKeyManagerServer

	mu      sync.RWMutex
	keys    map[string]*keyRecord
	auditMu sync.Mutex
}

func newPlugin() *plugin {
	return &plugin{keys: make(map[string]*keyRecord)}
}

func (p *plugin) audit(event, keyID string) error {
	path := os.Getenv("JLMIRROR_D3_KEYMANAGER_AUDIT")
	if path == "" {
		return status.Error(codes.FailedPrecondition, "evidence audit path is required")
	}
	p.auditMu.Lock()
	defer p.auditMu.Unlock()
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		return status.Errorf(codes.Internal, "open evidence audit: %v", err)
	}
	defer f.Close()
	if _, err := fmt.Fprintf(f, "%s:%s\n", event, keyID); err != nil {
		return status.Errorf(codes.Internal, "write evidence audit: %v", err)
	}
	return nil
}

func publicKeyRecord(id string, key *ecdsa.PrivateKey) (*keymanagerv1.PublicKey, error) {
	pkix, err := x509.MarshalPKIXPublicKey(&key.PublicKey)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal public key: %v", err)
	}
	sum := sha256.Sum256(pkix)
	return &keymanagerv1.PublicKey{
		Id:          id,
		Type:        keymanagerv1.KeyType_EC_P256,
		PkixData:    pkix,
		Fingerprint: hex.EncodeToString(sum[:]),
	}, nil
}

func clonePublicKey(in *keymanagerv1.PublicKey) *keymanagerv1.PublicKey {
	if in == nil {
		return nil
	}
	return &keymanagerv1.PublicKey{
		Id:          in.Id,
		Type:        in.Type,
		PkixData:    append([]byte(nil), in.PkixData...),
		Fingerprint: in.Fingerprint,
	}
}

func (p *plugin) GenerateKey(_ context.Context, req *keymanagerv1.GenerateKeyRequest) (*keymanagerv1.GenerateKeyResponse, error) {
	if req.GetKeyId() == "" {
		return nil, status.Error(codes.InvalidArgument, "key id is required")
	}
	if req.GetKeyType() != keymanagerv1.KeyType_EC_P256 {
		return nil, status.Errorf(codes.InvalidArgument, "unsupported key type %s", req.GetKeyType())
	}
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "generate private key: %v", err)
	}
	pub, err := publicKeyRecord(req.GetKeyId(), key)
	if err != nil {
		return nil, err
	}
	p.mu.Lock()
	p.keys[req.GetKeyId()] = &keyRecord{key: key, publicKey: pub}
	p.mu.Unlock()
	if err := p.audit("generate", req.GetKeyId()); err != nil {
		return nil, err
	}
	return &keymanagerv1.GenerateKeyResponse{PublicKey: clonePublicKey(pub)}, nil
}

func (p *plugin) GetPublicKey(_ context.Context, req *keymanagerv1.GetPublicKeyRequest) (*keymanagerv1.GetPublicKeyResponse, error) {
	p.mu.RLock()
	record := p.keys[req.GetKeyId()]
	p.mu.RUnlock()
	if record == nil {
		return nil, status.Errorf(codes.NotFound, "key %q not found", req.GetKeyId())
	}
	if err := p.audit("get-public", req.GetKeyId()); err != nil {
		return nil, err
	}
	return &keymanagerv1.GetPublicKeyResponse{PublicKey: clonePublicKey(record.publicKey)}, nil
}

func (p *plugin) GetPublicKeys(_ context.Context, _ *keymanagerv1.GetPublicKeysRequest) (*keymanagerv1.GetPublicKeysResponse, error) {
	p.mu.RLock()
	ids := make([]string, 0, len(p.keys))
	for id := range p.keys {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	publicKeys := make([]*keymanagerv1.PublicKey, 0, len(ids))
	for _, id := range ids {
		publicKeys = append(publicKeys, clonePublicKey(p.keys[id].publicKey))
	}
	p.mu.RUnlock()
	if err := p.audit("get-public-all", "all"); err != nil {
		return nil, err
	}
	return &keymanagerv1.GetPublicKeysResponse{PublicKeys: publicKeys}, nil
}

func (p *plugin) SignData(_ context.Context, req *keymanagerv1.SignDataRequest) (*keymanagerv1.SignDataResponse, error) {
	if len(req.GetData()) == 0 {
		return nil, status.Error(codes.InvalidArgument, "digest is required")
	}
	if req.GetPssOptions() != nil {
		return nil, status.Error(codes.InvalidArgument, "RSA-PSS is not supported by EC-P256 evidence signer")
	}
	if req.GetHashAlgorithm() != keymanagerv1.HashAlgorithm_SHA256 {
		return nil, status.Errorf(codes.InvalidArgument, "unsupported hash algorithm %s", req.GetHashAlgorithm())
	}
	p.mu.RLock()
	record := p.keys[req.GetKeyId()]
	p.mu.RUnlock()
	if record == nil {
		return nil, status.Errorf(codes.NotFound, "key %q not found", req.GetKeyId())
	}
	signature, err := ecdsa.SignASN1(rand.Reader, record.key, req.GetData())
	if err != nil {
		return nil, status.Errorf(codes.Internal, "sign digest: %v", err)
	}
	if err := p.audit("sign", req.GetKeyId()); err != nil {
		return nil, err
	}
	return &keymanagerv1.SignDataResponse{
		Signature:      signature,
		KeyFingerprint: record.publicKey.Fingerprint,
	}, nil
}

func main() {
	pluginmain.Serve(keymanagerv1.KeyManagerPluginServer(newPlugin()))
}
