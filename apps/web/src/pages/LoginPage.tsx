import { Box, Button, Heading, Input, Stack, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../auth/useAuth';

export function LoginPage() {
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.post('/auth/login', { email, password });
      await refresh();
      navigate('/');
    } catch {
      setError('Invalid credentials');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Box maxW="sm" mx="auto" mt={20} p={6} borderWidth={1} borderRadius="lg">
      <Heading size="lg" mb={4}>
        Sign in to Prism
      </Heading>
      <form onSubmit={handleSubmit}>
        <Stack gap={3}>
          <Input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && (
            <Text color="red.400" fontSize="sm">
              {error}
            </Text>
          )}
          <Button type="submit" colorPalette="blue" loading={submitting}>
            Sign in
          </Button>
        </Stack>
      </form>
    </Box>
  );
}
