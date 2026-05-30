package ru.bionicpro.reports.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.security.SecureRandom;
import java.util.Base64;

@Service
public class EncryptionService {

    @Value("${bionicpro.encryption.secret-key}")
    private String secretKey;

    private static final String ALGORITHM = "AES/CBC/PKCS5Padding";

    public String encrypt(String text) {
        try {
            byte[] iv = new byte[16];
            new SecureRandom().nextBytes(iv);
            IvParameterSpec ivSpec = new IvParameterSpec(iv);

            byte[] keyBytes = secretKey.getBytes();
            byte[] key = new byte[32];
            System.arraycopy(keyBytes, 0, key, 0, Math.min(keyBytes.length, 32));
            SecretKeySpec keySpec = new SecretKeySpec(key, "AES");

            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, ivSpec);
            byte[] encrypted = cipher.doFinal(text.getBytes());

            byte[] combined = new byte[iv.length + encrypted.length];
            System.arraycopy(iv, 0, combined, 0, iv.length);
            System.arraycopy(encrypted, 0, combined, iv.length, encrypted.length);

            return Base64.getEncoder().encodeToString(combined);
        } catch (Exception e) {
            throw new RuntimeException("Failed to encrypt", e);
        }
    }

    public String decrypt(String encryptedText) {
        try {
            byte[] combined = Base64.getDecoder().decode(encryptedText);
            byte[] iv = new byte[16];
            byte[] encrypted = new byte[combined.length - 16];
            System.arraycopy(combined, 0, iv, 0, 16);
            System.arraycopy(combined, 16, encrypted, 0, encrypted.length);

            byte[] keyBytes = secretKey.getBytes();
            byte[] key = new byte[32];
            System.arraycopy(keyBytes, 0, key, 0, Math.min(keyBytes.length, 32));
            SecretKeySpec keySpec = new SecretKeySpec(key, "AES");

            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.DECRYPT_MODE, keySpec, new IvParameterSpec(iv));
            byte[] decrypted = cipher.doFinal(encrypted);

            return new String(decrypted);
        } catch (Exception e) {
            throw new RuntimeException("Failed to decrypt", e);
        }
    }
}