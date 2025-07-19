import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Box, Container, Heading, Text, Input, Table, Thead, Tbody, Tr, Th, Td,
  TableContainer, Select, SimpleGrid, Stat, StatLabel, StatNumber, Flex,
  Divider, useDisclosure, Modal, ModalOverlay, ModalContent, ModalHeader,
  ModalCloseButton, ModalBody, ModalFooter, Button
} from '@chakra-ui/react';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, ResponsiveContainer
} from 'recharts';

interface Munro {
  id: number;
  name: string;
  summary: string;
  distance: number;
  time: number;
  grade: number;
  bog: number;
  start: string;
}

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <Box bg="white" border="1px solid #ccc" px={3} py={2} rounded="md" shadow="sm">
        <Text fontWeight="semibold">{payload[0].payload.name}</Text>
      </Box>
    );
  }
  return null;
};

export default function App() {
  const [munros, setMunros] = useState<Munro[]>([]);
  const [search, setSearch] = useState('');
  const [grade, setGrade] = useState('');
  const [bog, setBog] = useState('');
  const [sortKey, setSortKey] = useState('');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [selectedMunro, setSelectedMunro] = useState<Munro | null>(null);
  const { isOpen, onOpen, onClose } = useDisclosure();

  useEffect(() => {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (grade) params.append('grade', grade);
    if (bog) params.append('bog', bog);
    axios
      .get(`http://localhost:5000/api/munros?${params.toString()}`)
      .then((res) => {
        let data = res.data;
        if (sortKey) {
          data = [...data].sort((a, b) => {
            const aVal = sortKey === 'name' ? a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }) : a[sortKey];
            const bVal = sortKey === 'name' ? b.name.localeCompare(a.name, 'en', { sensitivity: 'base' }) : b[sortKey];
            return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
          });
        }
        setMunros(data);
      })
      .catch((err) => console.error(err));
  }, [search, grade, bog, sortKey, sortOrder]);

  const stats = {
    total: munros.length,
    avgDistance: munros.reduce((sum, m) => sum + m.distance, 0) / (munros.length || 1),
    avgTime: munros.reduce((sum, m) => sum + m.time, 0) / (munros.length || 1),
    avgGrade: munros.reduce((sum, m) => sum + m.grade, 0) / (munros.length || 1),
    avgBog: munros.reduce((sum, m) => sum + m.bog, 0) / (munros.length || 1),
  };

  return (
    <Box minH="100vh" bgGradient="linear(to-br, gray.50, white)">
      <Box bg="blue.700" color="white" py={6} px={6} shadow="md">
        <Heading size="lg">Munro Explorer Dashboard</Heading>
        <Text mt={2} fontSize="sm" color="blue.100">
          Discover and analyze Munro mountains in Scotland based on distance, difficulty, and more.
        </Text>
      </Box>

      <Container maxW="6xl" py={10}>
        <Heading size="md" mb={2}>Overview Statistics</Heading>
        <Divider mb={6} />
        <SimpleGrid columns={{ base: 2, md: 5 }} spacing={4} mb={10}>
          <Stat><StatLabel>Total Munros</StatLabel><StatNumber>{stats.total}</StatNumber></Stat>
          <Stat><StatLabel>Avg Distance</StatLabel><StatNumber>{stats.avgDistance.toFixed(1)}</StatNumber></Stat>
          <Stat><StatLabel>Avg Time</StatLabel><StatNumber>{stats.avgTime.toFixed(1)}</StatNumber></Stat>
          <Stat><StatLabel>Avg Grade</StatLabel><StatNumber>{stats.avgGrade.toFixed(1)}</StatNumber></Stat>
          <Stat><StatLabel>Avg Bog</StatLabel><StatNumber>{stats.avgBog.toFixed(1)}</StatNumber></Stat>
        </SimpleGrid>

        <Heading size="md" mb={2}>Distance vs Time</Heading>
        <Divider mb={6} />
        <Box h="300px" mb={10}>
          <ResponsiveContainer>
            <ScatterChart margin={{ top: 10, right: 30, bottom: 10, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="distance"
                name="Distance (km)"
                domain={[5, 40]}
                label={{ value: 'Distance (km)', position: 'insideBottomRight', offset: -5 }}
              />
              <YAxis
                type="number"
                dataKey="time"
                name="Time (hrs)"
                label={{ value: 'Time (hrs)', angle: -90, position: 'insideLeft' }}
              />
              <ChartTooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
              <Scatter
                name="Munros"
                data={munros}
                fill="#3182ce"
                isAnimationActive={false}
              />
            </ScatterChart>
          </ResponsiveContainer>
        </Box>

        <Heading size="md" mb={2}>Filters & Sorting</Heading>
        <Divider mb={4} />
        <Flex gap={4} wrap="wrap" mb={10}>
          <Input placeholder="Search by name..." value={search} onChange={(e) => setSearch(e.target.value)} w="full" maxW="250px" />
          <Select placeholder="Filter by grade" value={grade} onChange={(e) => setGrade(e.target.value)} maxW="180px">
            {[1, 2, 3, 4, 5].map(g => <option key={g} value={g}>{g}</option>)}
          </Select>
          <Select placeholder="Max bog" value={bog} onChange={(e) => setBog(e.target.value)} maxW="180px">
            {[2, 4, 6, 8, 10].map(b => <option key={b} value={b}>{b}</option>)}
          </Select>
          <Select placeholder="Sort by" value={sortKey} onChange={(e) => setSortKey(e.target.value)} maxW="180px">
            <option value="name">Name (A–Z)</option>
            <option value="distance">Distance</option>
            <option value="time">Time</option>
          </Select>
          <Select placeholder="Order" value={sortOrder} onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')} maxW="140px">
            <option value="asc">Asc</option>
            <option value="desc">Desc</option>
          </Select>
        </Flex>

        <Heading size="md" mb={2}>Munro List</Heading>
        <Divider mb={4} />
        <Box bg="white" border="1px solid" borderColor="blue.100" shadow="lg" rounded="2xl" overflow="hidden">
          <TableContainer maxH="500px" overflowY="auto">
            <Table size="sm" variant="simple">
              <Thead position="sticky" top={0} bg="blue.500" color="white" zIndex={1}>
                <Tr>
                  <Th color="white">Name</Th>
                  <Th textAlign="center" color="white">Distance (km)</Th>
                  <Th textAlign="center" color="white">Time (hrs)</Th>
                  <Th textAlign="center" color="white">Grade</Th>
                  <Th textAlign="center" color="white">Bog</Th>
                </Tr>
              </Thead>
              <Tbody>
                {munros.map((m) => (
                  <Tr key={m.id} _hover={{ bg: 'blue.50' }} cursor="pointer" onClick={() => { setSelectedMunro(m); onOpen(); }}>
                    <Td fontWeight="semibold">{m.name}</Td>
                    <Td textAlign="center">{m.distance}</Td>
                    <Td textAlign="center">{m.time}</Td>
                    <Td textAlign="center">{m.grade}</Td>
                    <Td textAlign="center">{m.bog}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </TableContainer>
        </Box>

        <Text mt={12} textAlign="center" fontSize="sm" color="gray.400">
          Built with Flask, React & Chakra UI — demo project by Dhruv
        </Text>

        <Modal isOpen={isOpen} onClose={onClose} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>{selectedMunro?.name}</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <Text fontSize="sm" whiteSpace="pre-wrap">{selectedMunro?.summary}</Text>
            </ModalBody>
            <ModalFooter>
              <Button onClick={onClose}>Close</Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </Container>
    </Box>
  );
}
