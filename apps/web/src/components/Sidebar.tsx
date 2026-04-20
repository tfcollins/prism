import { Box, Heading, Stack, Text } from '@chakra-ui/react';
import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Runs' },
  { to: '/projects', label: 'Projects' },
];

export function Sidebar() {
  return (
    <Box
      as="nav"
      w="220px"
      bg="#171923"
      borderRightWidth={1}
      borderRightColor="#2d3748"
      px={4}
      py={5}
    >
      <Heading size="md" color="#63b3ed" mb={6} letterSpacing="tight">
        Prism
      </Heading>
      <Stack gap={1}>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              display: 'block',
              padding: '6px 10px',
              borderRadius: '6px',
              fontSize: '13px',
              color: isActive ? '#fff' : '#a0aec0',
              background: isActive ? '#2d3748' : 'transparent',
              textDecoration: 'none',
            })}
          >
            {item.label}
          </NavLink>
        ))}
      </Stack>
      <Text mt={8} fontSize="xs" color="#4a5568" textTransform="uppercase">
        v0.2
      </Text>
    </Box>
  );
}
