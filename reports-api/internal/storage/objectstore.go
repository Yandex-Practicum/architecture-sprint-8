// Package storage persists generated reports in an S3-compatible object store
// (MinIO / Ceph) so repeat requests can be served from the CDN without touching
// the OLAP database again.
package storage

import (
	"bytes"
	"context"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

// ObjectStore is the small subset of S3 the reports API relies on.
type ObjectStore interface {
	Exists(ctx context.Context, key string) (bool, error)
	Put(ctx context.Context, key string, body []byte, contentType string) error
}

// MinioStore is an S3 (MinIO) backed ObjectStore.
type MinioStore struct {
	client *minio.Client
	bucket string
}

// NewMinioStore connects to an S3-compatible endpoint.
func NewMinioStore(endpoint, accessKey, secretKey, bucket string, useSSL bool) (*MinioStore, error) {
	client, err := minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(accessKey, secretKey, ""),
		Secure: useSSL,
	})
	if err != nil {
		return nil, err
	}
	return &MinioStore{client: client, bucket: bucket}, nil
}

// EnsureBucket creates the bucket if it does not exist yet (the init container
// normally does this; this is a best-effort safety net).
func (s *MinioStore) EnsureBucket(ctx context.Context) error {
	exists, err := s.client.BucketExists(ctx, s.bucket)
	if err != nil {
		return err
	}
	if !exists {
		return s.client.MakeBucket(ctx, s.bucket, minio.MakeBucketOptions{})
	}
	return nil
}

// Exists reports whether an object is already stored under key.
func (s *MinioStore) Exists(ctx context.Context, key string) (bool, error) {
	_, err := s.client.StatObject(ctx, s.bucket, key, minio.StatObjectOptions{})
	if err != nil {
		resp := minio.ToErrorResponse(err)
		if resp.StatusCode == 404 || resp.Code == "NoSuchKey" {
			return false, nil
		}
		return false, err
	}
	return true, nil
}

// Put uploads an object (overwriting any previous version of the same key).
func (s *MinioStore) Put(ctx context.Context, key string, body []byte, contentType string) error {
	_, err := s.client.PutObject(ctx, s.bucket, key, bytes.NewReader(body), int64(len(body)),
		minio.PutObjectOptions{ContentType: contentType})
	return err
}
