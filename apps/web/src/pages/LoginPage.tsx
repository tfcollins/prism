import { Box, Button, Flex, Heading, Input, Stack, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { Logo } from '../components/Logo';

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
    <Box
      maxW="sm"
      mx="auto"
      mt={20}
      p={6}
      borderWidth={1}
      borderRadius="lg"
      borderColor="var(--prism-border)"
      bg="var(--prism-bg-surface)"
    >
      <Flex direction="column" alignItems="center" mb={6}>
        <Logo size="lg" showWordmark={false} />
        <Heading size="lg" mt={4} letterSpacing="0.05em">
          Prism
        </Heading>
        <Text color="var(--prism-text-subtle)" fontSize="sm" mt={1}>
          Sign in to continue
        </Text>
      </Flex>
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
