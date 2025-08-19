import "leaflet/dist/leaflet.css";
import "./config/leaflet";

import { useEffect, useState } from "react";
import axios from "axios";
import {
  Box, Container, Heading, Text, Flex,
  Divider, useDisclosure, Modal, ModalOverlay, ModalContent, ModalHeader,
  ModalCloseButton, ModalBody, ModalFooter, Button, SimpleGrid, useColorModeValue
} from "@chakra-ui/react";

import { Munro } from "./types/munro";
import StatsPanel from "./components/dashboard/StatsPanel";
import ScatterPlot from "./components/dashboard/ScatterPlot";
import Filters from "./components/dashboard/Filters";
import MunroTable from "./components/dashboard/MunroTable";
import DetailsTab from "./features/details/DetailsTab";
import ChatTab, { ChatMessage, ChatRouteLink } from "./features/chat/ChatTab";

/* ---------- Topographic background (inline) ---------- */
function TopoBg({ size = 240, opacity = 0.20 }: { size?: number; opacity?: number }) {
  const stroke = useColorModeValue("#6b7280", "#9ca3af"); // light/dark friendly
  const svg = encodeURIComponent(`
    <svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}' viewBox='0 0 240 240'>
      <defs><style>.l{fill:none;stroke:${stroke};stroke-opacity:${opacity};stroke-width:1}</style></defs>
      <path class="l" d="M-10 20 Q 50 0 110 20 T 230 20" />
      <path class="l" d="M-10 50 Q 40 30 110 50 T 230 50" />
      <path class="l" d="M-10 80 Q 60 60 120 80 T 250 80" />
      <path class="l" d="M-10 110 Q 50 95 120 110 T 250 110" />
      <path class="l" d="M-10 140 Q 70 120 140 140 T 280 140" />
      <path class="l" d="M-10 170 Q 40 150 120 170 T 250 170" />
      <path class="l" d="M-10 200 Q 80 185 150 200 T 310 200" />
      <path class="l" d="M-10 230 Q 50 215 120 230 T 250 230" />
      <path class="l" d="M20 -10 C 40 40, 40 80, 20 140 S 0 220, 20 260" />
      <path class="l" d="M120 -10 C 140 30, 140 90, 120 140 S 100 210, 120 260" />
      <path class="l" d="M200 -10 C 220 50, 220 100, 200 160 S 180 230, 200 260" />
    </svg>
  `);

  return (
    <Box
      aria-hidden
      position="fixed"
      inset={0}
      zIndex={-1}
      pointerEvents="none"
      bgImage={`url("data:image/svg+xml;utf8,${svg}")`}
      bgRepeat="repeat"
      bgSize={`${size}px ${size}px`}
      filter="contrast(0.92)"
    />
  );
}
/* ----------------------------------------------------- */

export default function App() {
  const [munros, setMunros] = useState<Munro[]>([]);
  const [search, setSearch] = useState("");
  const [grade, setGrade] = useState("");
  const [bog, setBog] = useState("");
  const [sortKey, setSortKey] = useState("");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [selectedMunro, setSelectedMunro] = useState<Munro | null>(null);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [activeTab, setActiveTab] = useState<"dashboard" | "chat" | "details">("dashboard");

  // ✅ Persist chat history in App
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Listen for assistant messages emitted by ChatTab after it gets server response
  useEffect(() => {
    const handler = (ev: any) => {
      const { content, steps, routes } = ev.detail || {};
      setMessages((prev) => [...prev, { role: "assistant", content: content || "", steps, routes }]);
    };
    window.addEventListener("munro-chat-assistant", handler);
    return () => window.removeEventListener("munro-chat-assistant", handler);
  }, []);

  // Load munros for dashboard table
  useEffect(() => {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (grade) params.append("grade", grade);
    if (bog) params.append("bog", bog);
    axios
      .get(`http://localhost:5000/api/munros?${params.toString()}`)
      .then((res) => {
        let data = res.data as Munro[];
        if (sortKey) {
          data = [...data].sort((a, b) => {
            if (sortKey === "name") {
              const cmp = a.name.localeCompare(b.name, "en", { sensitivity: "base" });
              return sortOrder === "asc" ? cmp : -cmp;
            }
            const aVal = a[sortKey] as number;
            const bVal = b[sortKey] as number;
            return sortOrder === "asc" ? aVal - bVal : bVal - aVal;
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

  // When user submits a message in ChatTab
  const handleSend = async (text: string) => {
    setMessages((prev) => [...prev, { role: "user", content: text }]);
  };

  // Clicking a route button: fetch full record and open the Details tab
  const openRoute = async (route: ChatRouteLink) => {
    try {
      const res = await axios.get(`http://localhost:5000/api/munro/${route.id}`);
      const munro = res.data as Munro;
      setSelectedMunro(munro);
      setActiveTab("details");
    } catch {
      try {
        const res2 = await axios.get(`http://localhost:5000/api/munros?id=${route.id}`);
        const munro = (res2.data as Munro[])[0];
        if (munro) {
          setSelectedMunro(munro);
          setActiveTab("details");
        }
      } catch (e) {
        console.error("Failed to open route", e);
      }
    }
  };

  return (
    <>
      {/* one-time background */}
      <TopoBg size={240} opacity={0.20} />

      <Box minH="100vh" bgGradient="linear(to-br, gray.50, white)">
        {/* Header */}
        <Box bg="blue.700" color="white" py={6} px={6} shadow="md">
          <Heading size="lg">Munro Explorer Dashboard</Heading>
          <Text mt={2} fontSize="sm" color="blue.100">
            Discover and analyze Munro mountains in Scotland based on distance, difficulty, and more.
          </Text>
          <Flex mt={4} gap={4}>
            <Button
              variant={activeTab === "dashboard" ? "solid" : "outline"}
              onClick={() => setActiveTab("dashboard")}
              colorScheme="whiteAlpha"
            >
              Dashboard
            </Button>
            <Button
              variant={activeTab === "chat" ? "solid" : "outline"}
              onClick={() => setActiveTab("chat")}
              colorScheme="whiteAlpha"
            >
              Chat Assistant
            </Button>
            <Button
              variant={activeTab === "details" ? "solid" : "outline"}
              onClick={() => setActiveTab("details")}
              colorScheme="whiteAlpha"
            >
              Munro Details
            </Button>
          </Flex>
        </Box>

        <Container maxW="6xl" py={10}>
          {activeTab === "dashboard" ? (
            <>
              <Heading size="md" mb={2}>Overview Statistics</Heading>
              <Divider mb={6} />
              <StatsPanel stats={stats} />

              <Heading size="md" mb={2}>Distance vs Time</Heading>
              <Divider mb={6} />
              <ScatterPlot data={munros} />

              <Heading size="md" mb={2}>Filters & Sorting</Heading>
              <Divider mb={4} />
              <Filters
                search={search}
                grade={grade}
                bog={bog}
                sortKey={sortKey}
                sortOrder={sortOrder}
                onSearch={setSearch}
                onGrade={setGrade}
                onBog={setBog}
                onSortKey={setSortKey}
                onSortOrder={setSortOrder}
              />

              <Heading size="md" mb={2}>Munro List</Heading>
              <Divider mb={4} />
              <MunroTable
                munros={munros}
                onRowClick={(m) => { setSelectedMunro(m); onOpen(); }}
              />
            </>
          ) : activeTab === "chat" ? (
            <ChatTab
              messages={messages}
              onSend={handleSend}
              onOpenRoute={openRoute}
            />
          ) : (
            <DetailsTab initialMunro={selectedMunro} />
          )}

          <Text mt={12} textAlign="center" fontSize="sm" color="gray.400">
            Built with Flask, React & Chakra UI — demo project by Dhruv
          </Text>

          {/* Modal for quick preview */}
          <Modal isOpen={isOpen} onClose={onClose} size="lg">
            <ModalOverlay />
            <ModalContent>
              <ModalHeader>{selectedMunro?.title || selectedMunro?.name}</ModalHeader>
              <ModalCloseButton />
              <ModalBody>
                <Text mb={4} fontSize="sm" whiteSpace="pre-wrap">{selectedMunro?.summary}</Text>
                <SimpleGrid columns={2} spacing={4}>
                  <Flex align="center" gap={3}><Text><strong>Distance:</strong> {selectedMunro?.distance} km</Text></Flex>
                  <Flex align="center" gap={3}><Text><strong>Time:</strong> {selectedMunro?.time} hrs</Text></Flex>
                  <Flex align="center" gap={3}><Text><strong>Grade:</strong> {selectedMunro?.grade}</Text></Flex>
                  <Flex align="center" gap={3}><Text><strong>Bog:</strong> {selectedMunro?.bog}/5</Text></Flex>
                  <Flex align="center" gap={3} gridColumn="span 2"><Text><strong>Start Point:</strong> {selectedMunro?.start}</Text></Flex>
                </SimpleGrid>
              </ModalBody>
              <ModalFooter>
                <Flex gap={3}>
                  <Button variant="ghost" onClick={onClose}>Close</Button>
                  <Button
                    colorScheme="blue"
                    onClick={() => {
                      setActiveTab("details");
                      onClose();
                    }}
                  >
                    View in Details Tab
                  </Button>
                </Flex>
              </ModalFooter>
            </ModalContent>
          </Modal>
        </Container>
      </Box>
    </>
  );
}
