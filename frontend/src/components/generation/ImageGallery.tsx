import { useCallback, useEffect, useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  Filter,
  X,
  XCircle,
  ZoomIn,
} from 'lucide-react';
// Button available if needed
import type { GeneratedImage, ValidationCategoryDetail } from '@/api/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PASS_THRESHOLD = 70;

type ImageStatus = 'accepted' | 'rejected' | 'unscored';

function classifyImage(img: GeneratedImage): ImageStatus {
  if (img.validation_score == null) return 'unscored';
  return img.validation_score >= PASS_THRESHOLD ? 'accepted' : 'rejected';
}

function imageUrl(img: GeneratedImage) {
  const outputIdx = img.file_path.indexOf('output/');
  if (outputIdx !== -1) return '/' + img.file_path.slice(outputIdx);
  return img.file_path.startsWith('/') ? img.file_path : '/' + img.file_path;
}

// ---------------------------------------------------------------------------
// Filter type
// ---------------------------------------------------------------------------

type FilterMode = 'all' | 'accepted' | 'rejected';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ImageGalleryProps {
  images: GeneratedImage[];
  requestId: string;
  /** Overall validation categories (from the request-level validation). */
  validationCategories?: ValidationCategoryDetail[];
}

// ---------------------------------------------------------------------------
// Main Gallery
// ---------------------------------------------------------------------------

export function ImageGallery({
  images,
  requestId: _requestId,
  validationCategories,
}: ImageGalleryProps) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [filter, setFilter] = useState<FilterMode>('all');

  // Sort chronologically
  const sorted = [...images].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );

  const filtered =
    filter === 'all' ? sorted : sorted.filter((img) => classifyImage(img) === filter);

  const acceptedCount = sorted.filter((img) => classifyImage(img) === 'accepted').length;
  const rejectedCount = sorted.filter((img) => classifyImage(img) === 'rejected').length;

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      {sorted.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-4 h-4 text-[var(--muted-foreground)]" />
          <FilterPill
            active={filter === 'all'}
            onClick={() => setFilter('all')}
            label={`All (${sorted.length})`}
          />
          {acceptedCount > 0 && (
            <FilterPill
              active={filter === 'accepted'}
              onClick={() => setFilter('accepted')}
              label={`Accepted (${acceptedCount})`}
              variant="success"
            />
          )}
          {rejectedCount > 0 && (
            <FilterPill
              active={filter === 'rejected'}
              onClick={() => setFilter('rejected')}
              label={`Rejected (${rejectedCount})`}
              variant="destructive"
            />
          )}
        </div>
      )}

      {/* Thumbnail grid */}
      {filtered.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)] text-center py-8">
          No images match this filter.
        </p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {filtered.map((img) => {
            const globalIdx = sorted.indexOf(img);
            const status = classifyImage(img);
            return (
              <GalleryCard
                key={img.id}
                img={img}
                index={globalIdx}
                status={status}
                onClick={() => setLightboxIndex(globalIdx)}
              />
            );
          })}
        </div>
      )}

      {/* Lightbox */}
      {lightboxIndex !== null && (
        <ImageLightbox
          images={sorted}
          currentIndex={lightboxIndex}
          validationCategories={validationCategories}
          onClose={() => setLightboxIndex(null)}
          onNavigate={setLightboxIndex}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter Pill
// ---------------------------------------------------------------------------

function FilterPill({
  active,
  onClick,
  label,
  variant,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  variant?: 'success' | 'destructive';
}) {
  const baseClass =
    'px-3 py-1 rounded-full text-xs font-medium transition-all cursor-pointer select-none border';
  const activeClass = active
    ? variant === 'success'
      ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-400'
      : variant === 'destructive'
        ? 'bg-red-500/20 border-red-500/60 text-red-400'
        : 'bg-[var(--foreground)]/10 border-[var(--foreground)]/40 text-[var(--foreground)]'
    : 'bg-transparent border-[var(--border)] text-[var(--muted-foreground)] hover:border-[var(--foreground)]/40';

  return (
    <button onClick={onClick} className={`${baseClass} ${activeClass}`}>
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Gallery Card (thumbnail)
// ---------------------------------------------------------------------------

function GalleryCard({
  img,
  index,
  status,
  onClick,
}: {
  img: GeneratedImage;
  index: number;
  status: ImageStatus;
  onClick: () => void;
}) {
  const borderClass =
    status === 'accepted'
      ? 'ring-2 ring-emerald-500/60'
      : status === 'rejected'
        ? 'ring-2 ring-red-500/60'
        : '';

  return (
    <button
      onClick={onClick}
      className={`group relative rounded-md overflow-hidden border hover:ring-2 hover:ring-[var(--ring)] transition-all text-left ${borderClass}`}
    >
      <img
        src={imageUrl(img)}
        alt={`Attempt ${index + 1}`}
        className="w-full aspect-square object-cover"
      />

      {/* Status indicator - top left */}
      <div className="absolute top-2 left-2 flex flex-col gap-1">
        <Badge variant="secondary" className="text-xs">
          #{index + 1}
        </Badge>
        <Badge variant="outline" className="text-xs bg-[var(--background)]/80">
          {img.provider}
        </Badge>
      </div>

      {/* Status badge - top right */}
      <div className="absolute top-2 right-2 flex flex-col items-end gap-1">
        {status === 'accepted' && (
          <Badge variant="success" className="text-xs flex items-center gap-1">
            <Check className="w-3 h-3" />
            Accepted
          </Badge>
        )}
        {status === 'rejected' && (
          <Badge variant="destructive" className="text-xs flex items-center gap-1">
            <XCircle className="w-3 h-3" />
            Rejected
          </Badge>
        )}
        {img.validation_score != null && (
          <Badge
            variant={img.validation_score >= PASS_THRESHOLD ? 'success' : 'destructive'}
            className="text-xs"
          >
            {img.validation_score.toFixed(0)}
          </Badge>
        )}
      </div>

      {/* Hover overlay */}
      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center gap-3">
        <span className="text-white opacity-0 group-hover:opacity-100 text-sm font-medium drop-shadow-md transition-opacity flex items-center gap-1">
          <ZoomIn className="w-4 h-4" />
          Enlarge
        </span>
        <a
          href={imageUrl(img)}
          download
          className="opacity-0 group-hover:opacity-100 text-white hover:text-gray-200 transition-opacity drop-shadow-md"
          title="Download"
          onClick={(e) => e.stopPropagation()}
        >
          <Download className="w-5 h-5" />
        </a>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Lightbox with thumbnail strip
// ---------------------------------------------------------------------------

function ImageLightbox({
  images,
  currentIndex,
  validationCategories,
  onClose,
  onNavigate,
}: {
  images: GeneratedImage[];
  currentIndex: number;
  validationCategories?: ValidationCategoryDetail[];
  onClose: () => void;
  onNavigate: (index: number) => void;
}) {
  const img = images[currentIndex];
  const status = classifyImage(img);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < images.length - 1;
  const thumbStripRef = useRef<HTMLDivElement>(null);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft' && hasPrev) onNavigate(currentIndex - 1);
      if (e.key === 'ArrowRight' && hasNext) onNavigate(currentIndex + 1);
    },
    [onClose, onNavigate, currentIndex, hasPrev, hasNext],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Auto-scroll thumbnail strip to keep active thumb visible
  useEffect(() => {
    if (!thumbStripRef.current) return;
    const activeThumb = thumbStripRef.current.children[currentIndex] as HTMLElement | undefined;
    if (activeThumb) {
      activeThumb.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
        inline: 'center',
      });
    }
  }, [currentIndex]);

  // Build rejection reasons for the current image
  const rejectionReasons: string[] = [];
  if (status === 'rejected' && validationCategories) {
    for (const cat of validationCategories) {
      if (!cat.passed) {
        const reason = cat.reasoning || cat.details || cat.category;
        if (reason) rejectionReasons.push(reason);
      }
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/85 flex flex-col items-center justify-center"
      onClick={onClose}
    >
      {/* Top bar: close + counter */}
      <div className="absolute top-4 left-4 right-4 flex items-center justify-between z-10">
        <span className="text-white/70 text-sm font-medium">
          {currentIndex + 1} / {images.length}
        </span>
        <button onClick={onClose} className="text-white/70 hover:text-white transition-colors">
          <X className="w-6 h-6" />
        </button>
      </div>

      {/* Main image area */}
      <div
        className="relative flex-1 flex items-center justify-center w-full px-16 py-16"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Navigation arrows */}
        {hasPrev && (
          <button
            onClick={() => onNavigate(currentIndex - 1)}
            className="absolute left-4 top-1/2 -translate-y-1/2 text-white/60 hover:text-white transition-colors bg-black/40 hover:bg-black/60 rounded-full p-2"
          >
            <ChevronLeft className="w-8 h-8" />
          </button>
        )}
        {hasNext && (
          <button
            onClick={() => onNavigate(currentIndex + 1)}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-white/60 hover:text-white transition-colors bg-black/40 hover:bg-black/60 rounded-full p-2"
          >
            <ChevronRight className="w-8 h-8" />
          </button>
        )}

        <div className="flex flex-col items-center gap-4 max-w-4xl w-full">
          {/* Image with status border */}
          <div
            className={`relative rounded-lg overflow-hidden ${
              status === 'accepted'
                ? 'ring-3 ring-emerald-500/70'
                : status === 'rejected'
                  ? 'ring-3 ring-red-500/70'
                  : ''
            }`}
          >
            <img
              src={imageUrl(img)}
              alt={`Attempt ${currentIndex + 1}`}
              className="max-h-[60vh] rounded-lg object-contain"
            />
          </div>

          {/* Info bar */}
          <div className="flex flex-wrap items-center justify-between w-full gap-3 text-white text-sm">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="secondary">Attempt #{currentIndex + 1}</Badge>
              <Badge variant="outline" className="text-white border-white/40">
                {img.provider}
              </Badge>
              {status === 'accepted' && (
                <Badge variant="success" className="flex items-center gap-1">
                  <Check className="w-3 h-3" />
                  Accepted
                </Badge>
              )}
              {status === 'rejected' && (
                <Badge variant="destructive" className="flex items-center gap-1">
                  <XCircle className="w-3 h-3" />
                  Rejected
                </Badge>
              )}
              {img.validation_score != null && (
                <Badge variant={img.validation_score >= PASS_THRESHOLD ? 'success' : 'destructive'}>
                  Score: {img.validation_score.toFixed(1)}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-3">
              <span className="text-white/50">
                {img.width}x{img.height}
              </span>
              <a
                href={imageUrl(img)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-white/70 hover:text-white transition-colors"
                title="Open in new tab"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="w-4 h-4" />
              </a>
              <a
                href={imageUrl(img)}
                download
                className="flex items-center gap-1 text-white/70 hover:text-white transition-colors"
                title="Download image"
                onClick={(e) => e.stopPropagation()}
              >
                <Download className="w-4 h-4" />
              </a>
            </div>
          </div>

          {/* Rejection reasons */}
          {status === 'rejected' && rejectionReasons.length > 0 && (
            <div className="w-full bg-red-950/40 border border-red-500/30 rounded-md p-3 space-y-1">
              <p className="text-xs font-medium text-red-400 uppercase tracking-wide">
                Rejection Reasons
              </p>
              <ul className="space-y-1">
                {rejectionReasons.map((reason, i) => (
                  <li key={i} className="text-sm text-red-200/80 flex items-start gap-2">
                    <XCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-red-400" />
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Prompt used */}
          {img.prompt_used && (
            <details className="w-full text-xs">
              <summary className="cursor-pointer text-white/50 hover:text-white/80 transition-colors">
                View prompt used
              </summary>
              <pre className="mt-2 bg-white/5 border border-white/10 p-3 rounded-md overflow-auto max-h-32 whitespace-pre-wrap text-white/70">
                {img.prompt_used}
              </pre>
            </details>
          )}
        </div>
      </div>

      {/* Thumbnail strip */}
      {images.length > 1 && (
        <div className="w-full px-4 pb-4" onClick={(e) => e.stopPropagation()}>
          <div ref={thumbStripRef} className="flex gap-2 overflow-x-auto py-2 px-2 justify-center">
            {images.map((thumb, i) => {
              const thumbStatus = classifyImage(thumb);
              const isActive = i === currentIndex;
              return (
                <button
                  key={thumb.id}
                  onClick={() => onNavigate(i)}
                  className={`relative flex-shrink-0 w-16 h-16 rounded-md overflow-hidden border-2 transition-all ${
                    isActive
                      ? 'border-white scale-110 shadow-lg shadow-white/20'
                      : thumbStatus === 'accepted'
                        ? 'border-emerald-500/50 opacity-70 hover:opacity-100'
                        : thumbStatus === 'rejected'
                          ? 'border-red-500/50 opacity-70 hover:opacity-100'
                          : 'border-white/20 opacity-50 hover:opacity-100'
                  }`}
                >
                  <img
                    src={imageUrl(thumb)}
                    alt={`Thumb ${i + 1}`}
                    className="w-full h-full object-cover"
                  />
                  {/* Tiny status dot */}
                  {thumbStatus !== 'unscored' && (
                    <div
                      className={`absolute bottom-0.5 right-0.5 w-2.5 h-2.5 rounded-full border border-black/40 ${
                        thumbStatus === 'accepted' ? 'bg-emerald-500' : 'bg-red-500'
                      }`}
                    />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
