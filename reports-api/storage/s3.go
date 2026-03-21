package storage

import (
	"bytes"
	"context"
	"io"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"

	"reports-api/internal/config"
)

type S3Storage struct {
	client *minio.Client
	bucket string
}

func NewS3(cfg config.Config) (*S3Storage, error) {
	cli, err := minio.New(cfg.S3Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.S3AccessKey, cfg.S3SecretKey, ""),
		Secure: false,
	})
	if err != nil {
		return nil, err
	}
	return &S3Storage{client: cli, bucket: cfg.S3Bucket}, nil
}

func (s *S3Storage) Exists(ctx context.Context, key string) (bool, error) {
	_, err := s.client.StatObject(ctx, s.bucket, key, minio.StatObjectOptions{})
	if err != nil {
		if minio.ToErrorResponse(err).Code == "NoSuchKey" {
			return false, nil
		}
		return false, err
	}
	return true, nil
}

func (s *S3Storage) Put(ctx context.Context, key string, data []byte) error {
	reader := bytes.NewReader(data)
	_, err := s.client.PutObject(ctx, s.bucket, key, reader, int64(len(data)), minio.PutObjectOptions{
		ContentType: "text/markdown; charset=utf-8",
	})
	return err
}

func (s *S3Storage) Get(ctx context.Context, key string) (io.ReadCloser, error) {
	return s.client.GetObject(ctx, s.bucket, key, minio.GetObjectOptions{})
}
