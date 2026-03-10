import { useMemo } from 'react';
import {
  ReactFlow,
  Handle,
  Position,
  Background,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

type NodeStatus = 'pending' | 'running' | 'completed' | 'error';

type PipelineNodeData = {
  label: string;
  nodeStatus: NodeStatus;
  isEnd?: boolean;
} & Record<string, unknown>;

const HANDLE_STYLE = { opacity: 0, pointerEvents: 'none' as const };

const NODE_CLASSES: Record<NodeStatus, string> = {
  pending:
    'border border-gray-200 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-400 bg-white',
  running:
    'border-2 border-blue-400 rounded-lg px-3 py-1.5 text-xs font-medium text-white bg-blue-500 animate-pulse',
  completed:
    'border-2 border-green-600 rounded-lg px-3 py-1.5 text-xs font-medium text-white bg-green-600',
  error: 'border-2 border-red-500 rounded-lg px-3 py-1.5 text-xs font-medium text-white bg-red-500',
};

function PipelineNode({ data }: NodeProps) {
  const { label, nodeStatus, isEnd } = data as PipelineNodeData;

  if (isEnd) {
    const cls =
      nodeStatus === 'completed'
        ? 'border border-gray-400 rounded px-2 py-0.5 text-[10px] font-semibold text-gray-500 bg-gray-50'
        : 'border border-gray-200 rounded px-2 py-0.5 text-[10px] font-semibold text-gray-300 bg-white';
    return (
      <>
        <Handle type="target" position={Position.Left} style={HANDLE_STYLE} id="left" />
        <Handle type="target" position={Position.Top} style={HANDLE_STYLE} id="top" />
        <div className={cls}>END</div>
      </>
    );
  }

  return (
    <>
      <Handle type="target" position={Position.Left} style={HANDLE_STYLE} />
      <Handle type="target" position={Position.Bottom} style={HANDLE_STYLE} id="bottom-in" />
      <div className={NODE_CLASSES[nodeStatus]}>
        {nodeStatus === 'completed' && '✓ '}
        {label}
      </div>
      <Handle type="source" position={Position.Right} style={HANDLE_STYLE} />
      <Handle type="source" position={Position.Bottom} style={HANDLE_STYLE} id="bottom-out" />
    </>
  );
}

const nodeTypes: NodeTypes = { pipeline: PipelineNode };

function resolveStatus(
  nodeId: string,
  currentAgent: string | null,
  overallStatus: string,
  completedAgents: Set<string>,
): NodeStatus {
  if (overallStatus === 'failed' && currentAgent === nodeId) return 'error';
  if (completedAgents.has(nodeId)) return 'completed';
  if (currentAgent === nodeId && overallStatus !== 'completed' && overallStatus !== 'failed')
    return 'running';
  return 'pending';
}

interface DAGVisualizerProps {
  currentAgent: string | null;
  status: string;
  agentTrace: Array<Record<string, unknown>>;
  runType?: string;
}

// Portrait pipeline nodes
const PORTRAIT_NODE_DEFS = [
  { id: 'extraction', label: 'Extraction', x: 0, y: 60 },
  { id: 'research', label: 'Research', x: 155, y: 60 },
  { id: 'face_search', label: 'Face Search', x: 310, y: 60 },
  { id: 'prompt_generation', label: 'Prompt Gen', x: 465, y: 60 },
  { id: 'image_generation', label: 'Image Gen', x: 620, y: 60 },
  { id: 'validation', label: 'Validation', x: 775, y: 60 },
  { id: 'facial_compositing', label: 'Facial Compositing', x: 930, y: 60 },
  { id: 'export', label: 'Export', x: 1080, y: 60 },
];

const PORTRAIT_END_NODE = { id: 'END', x: 1225, y: 60 };

// Story pipeline nodes — matches graph.py
// Row 1 (y=10): optional branches (image_to_story, ref_image_analysis)
// Row 2 (y=80): main pipeline path
// Row 3 (y=150): narration / video / export
const STORY_NODE_DEFS = [
  { id: 'story_orchestrator', label: 'Orchestrator', x: 0, y: 80 },
  { id: 'image_to_story', label: 'Img→Story', x: 170, y: 10 },
  { id: 'reference_image_analysis', label: 'Ref Analysis', x: 170, y: 150 },
  { id: 'character_extraction', label: 'Characters', x: 340, y: 80 },
  { id: 'scene_decomposition', label: 'Scenes', x: 490, y: 80 },
  { id: 'scene_prompt_generation', label: 'Prompt Gen', x: 640, y: 80 },
  { id: 'scene_image_generation', label: 'Image Gen', x: 800, y: 80 },
  { id: 'storyboard_coherence', label: 'Coherence', x: 960, y: 80 },
  { id: 'narration_script', label: 'Narration', x: 1110, y: 80 },
  { id: 'narration_audio', label: 'Audio', x: 1230, y: 80 },
  { id: 'video_assembly', label: 'Video', x: 1340, y: 80 },
  { id: 'storyboard_export', label: 'Export', x: 1450, y: 80 },
];

const STORY_END_NODE = { id: 'END', x: 1570, y: 80 };

const GRAY_MARKER = { type: MarkerType.ArrowClosed, width: 10, height: 10 };
const RED_MARKER = { type: MarkerType.ArrowClosed, width: 10, height: 10, color: '#ef4444' };
const AMBER_MARKER = { type: MarkerType.ArrowClosed, width: 10, height: 10, color: '#d97706' };

const EDGE_STYLE_DIRECT = { stroke: '#9ca3af', strokeWidth: 1.5 };
const EDGE_STYLE_COND = { stroke: '#6b7280', strokeWidth: 1.5, strokeDasharray: '5 3' };
const EDGE_STYLE_ERROR = { stroke: '#ef4444', strokeWidth: 1.5, strokeDasharray: '5 3' };
const EDGE_STYLE_REGEN = { stroke: '#d97706', strokeWidth: 1.5, strokeDasharray: '5 3' };

const LABEL_BG = { fill: '#fff', fillOpacity: 0.85 };
const LABEL_GRAY = { fontSize: 9, fill: '#6b7280' };
const LABEL_RED = { fontSize: 9, fill: '#ef4444' };
const LABEL_AMBER = { fontSize: 9, fill: '#d97706' };

const PORTRAIT_EDGES: Edge[] = [
  // Direct happy-path edges
  {
    id: 'e-ex-re',
    source: 'extraction',
    target: 'research',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 'e-re-fsr',
    source: 'research',
    target: 'face_search',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 'e-fsr-pg',
    source: 'face_search',
    target: 'prompt_generation',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 'e-pg-ig',
    source: 'prompt_generation',
    target: 'image_generation',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 'e-fs-ex',
    source: 'facial_compositing',
    target: 'export',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 'e-ex-end',
    source: 'export',
    target: 'END',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  // Conditional: image_generation
  {
    id: 'e-ig-va',
    source: 'image_generation',
    target: 'validation',
    label: 'validate',
    labelStyle: LABEL_GRAY,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_COND,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 'e-ig-end',
    source: 'image_generation',
    target: 'END',
    sourceHandle: 'bottom-out',
    targetHandle: 'top',
    label: 'error',
    labelStyle: LABEL_RED,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_ERROR,
    markerEnd: RED_MARKER,
    type: 'smoothstep',
  },
  // Conditional: validation
  {
    id: 'e-va-fs',
    source: 'validation',
    target: 'facial_compositing',
    label: 'continue',
    labelStyle: LABEL_GRAY,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_COND,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 'e-va-pg',
    source: 'validation',
    target: 'prompt_generation',
    sourceHandle: 'bottom-out',
    targetHandle: 'bottom-in',
    label: 'regenerate',
    labelStyle: LABEL_AMBER,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_REGEN,
    markerEnd: AMBER_MARKER,
    type: 'smoothstep',
  },
  {
    id: 'e-va-end',
    source: 'validation',
    target: 'END',
    sourceHandle: 'bottom-out',
    targetHandle: 'left',
    label: 'error',
    labelStyle: LABEL_RED,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_ERROR,
    markerEnd: RED_MARKER,
    type: 'smoothstep',
  },
];

const STORY_EDGES: Edge[] = [
  // Orchestrator → conditional branches
  {
    id: 's-orch-char',
    source: 'story_orchestrator',
    target: 'character_extraction',
    label: 'continue',
    labelStyle: LABEL_GRAY,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-orch-i2s',
    source: 'story_orchestrator',
    target: 'image_to_story',
    label: 'image',
    labelStyle: LABEL_GRAY,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_COND,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-orch-ref',
    source: 'story_orchestrator',
    target: 'reference_image_analysis',
    label: 'ref imgs',
    labelStyle: LABEL_GRAY,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_COND,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-orch-end',
    source: 'story_orchestrator',
    target: 'END',
    sourceHandle: 'bottom-out',
    targetHandle: 'top',
    label: 'error',
    labelStyle: LABEL_RED,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_ERROR,
    markerEnd: RED_MARKER,
    type: 'smoothstep',
  },
  // image_to_story → character_extraction (or ref analysis)
  {
    id: 's-i2s-char',
    source: 'image_to_story',
    target: 'character_extraction',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-i2s-ref',
    source: 'image_to_story',
    target: 'reference_image_analysis',
    label: 'ref imgs',
    labelStyle: LABEL_GRAY,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_COND,
    markerEnd: GRAY_MARKER,
  },
  // reference_image_analysis → character_extraction
  {
    id: 's-ref-char',
    source: 'reference_image_analysis',
    target: 'character_extraction',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  // Main pipeline path
  {
    id: 's-char-scene',
    source: 'character_extraction',
    target: 'scene_decomposition',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-scene-prompt',
    source: 'scene_decomposition',
    target: 'scene_prompt_generation',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-prompt-img',
    source: 'scene_prompt_generation',
    target: 'scene_image_generation',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-img-coh',
    source: 'scene_image_generation',
    target: 'storyboard_coherence',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  // Coherence → conditional: narration (TTS) / regen / export
  {
    id: 's-coh-narr',
    source: 'storyboard_coherence',
    target: 'narration_script',
    label: 'narration',
    labelStyle: LABEL_GRAY,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_COND,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-coh-exp',
    source: 'storyboard_coherence',
    target: 'storyboard_export',
    sourceHandle: 'bottom-out',
    targetHandle: 'bottom-in',
    label: 'no TTS',
    labelStyle: LABEL_GRAY,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_COND,
    markerEnd: GRAY_MARKER,
    type: 'smoothstep',
  },
  {
    id: 's-coh-regen',
    source: 'storyboard_coherence',
    target: 'scene_prompt_generation',
    sourceHandle: 'bottom-out',
    targetHandle: 'bottom-in',
    label: 'regenerate',
    labelStyle: LABEL_AMBER,
    labelBgStyle: LABEL_BG,
    style: EDGE_STYLE_REGEN,
    markerEnd: AMBER_MARKER,
    type: 'smoothstep',
  },
  // Narration → Audio → Video → Export
  {
    id: 's-narr-audio',
    source: 'narration_script',
    target: 'narration_audio',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-audio-video',
    source: 'narration_audio',
    target: 'video_assembly',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-video-exp',
    source: 'video_assembly',
    target: 'storyboard_export',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
  {
    id: 's-exp-end',
    source: 'storyboard_export',
    target: 'END',
    style: EDGE_STYLE_DIRECT,
    markerEnd: GRAY_MARKER,
  },
];

export function DAGVisualizer({ currentAgent, status, agentTrace, runType }: DAGVisualizerProps) {
  const isStory = runType === 'creative_story';
  const nodeDefs = isStory ? STORY_NODE_DEFS : PORTRAIT_NODE_DEFS;
  const endNodeDef = isStory ? STORY_END_NODE : PORTRAIT_END_NODE;
  const edges = isStory ? STORY_EDGES : PORTRAIT_EDGES;

  const completedAgents = useMemo(
    () => new Set(agentTrace.map((t) => String(t.agent))),
    [agentTrace],
  );

  const nodes: Node[] = useMemo(() => {
    const mainNodes = nodeDefs.map((def) => ({
      id: def.id,
      type: 'pipeline' as const,
      position: { x: def.x, y: def.y },
      data: {
        label: def.label,
        nodeStatus: resolveStatus(def.id, currentAgent, status, completedAgents),
      },
      draggable: false,
      selectable: false,
    }));

    const endReached = status === 'completed' || status === 'failed';
    const endNode: Node = {
      id: 'END',
      type: 'pipeline',
      position: { x: endNodeDef.x, y: endNodeDef.y },
      data: {
        label: 'END',
        nodeStatus: endReached ? ('completed' as NodeStatus) : ('pending' as NodeStatus),
        isEnd: true,
      },
      draggable: false,
      selectable: false,
    };

    return [...mainNodes, endNode];
  }, [currentAgent, status, completedAgents, nodeDefs, endNodeDef]);

  return (
    <div
      className="rounded-lg border border-[var(--border)] bg-white overflow-hidden"
      style={{ height: isStory ? 320 : 260 }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        preventScrolling={false}
        minZoom={0.4}
        maxZoom={1.2}
        attributionPosition="bottom-right"
      >
        <Background color="#f3f4f6" gap={20} size={1} />
      </ReactFlow>
    </div>
  );
}
