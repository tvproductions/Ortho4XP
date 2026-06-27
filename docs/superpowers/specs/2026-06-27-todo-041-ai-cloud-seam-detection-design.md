# TODO-041 AI Cloud and Seam Detection Design

## Goal

Improve provider imagery scoring so downloaded textures can identify likely
cloud, haze, and seam defects before they become visible scenery artifacts.

## Interpretation of "AI"

For this repository, "AI" means image-intelligence heuristics in the default
implementation, not a required machine-learning runtime. The baseline repo has
no provider-quality analysis. ORTHO4XP_V3 adds an `O4_Provider_Score` module,
but its cloud and seam logic is deterministic NumPy/Pillow analysis rather than
model inference. This project keeps that lean default while leaving a clean
interface for optional future computer-vision or ML backends.

The default implementation must not add PyTorch, SAM, OpenCV, ONNX Runtime,
OpenVINO, or model checkpoint dependencies. Those tools remain candidates for a
future optional backend when a trained classifier or advanced image registration
has clear value.

## Scope

This work extends the existing provider scoring surface:

- `O4_Provider_Score_Clouds.py` for cloud, haze, and blue-sky exclusion metrics;
- `O4_Provider_Score_Seams.py` for edge and seam-risk metrics;
- `O4_Provider_Score_Models.py` for metric/detail contracts;
- `O4_Provider_Score_Metrics.py` for orchestration;
- `O4_Provider_Scoring.py` for logging and global quality scoring.

The work does not choose or blend imagery providers by itself. It produces
better evidence for the existing provider score log and the provider-failover
surface added by TODO-040. Texture boundaries are where seams are observed; this
feature identifies likely bad boundaries rather than changing tile layout.

## Cloud Detection

Cloud scoring combines three deterministic criteria:

1. dense cloud pixels: high luminance with low saturation;
2. atmospheric veil or fog: moderately high luminance, low saturation, and low
   local luminance variance;
3. blue-sky exclusion: pixels whose blue channel clearly dominates are not
   counted as cloud simply because they are bright.

The score tolerates up to 5 percent cloud coverage before applying a
penalty. That threshold prevents small white objects, isolated haze, and
incidental bright features from dragging down an otherwise usable texture.

The metric exposes structured details such as total cloud coverage, dense
cloud coverage, veil coverage, and blue-sky excluded coverage. These details are
for diagnostics and future debug visualizations; the existing global score still
receives a single `clouds` risk value.

## Seam Detection

Seam scoring analyzes all four edges independently. A single bad edge is
enough to create a visible texture boundary, so averaging all edges into one
mean can hide the defect.

The metric combines:

- edge-to-interior luminance drift;
- edge-to-interior RGB drift;
- worst single-edge drift;
- abrupt local border gradients near each edge;
- optional neighbor-edge comparison when adjacent cached or generated texture
  edge samples are available through a small context object.

Neighbor-edge comparison is more valuable than adding a generic ML dependency.
It directly measures what users see: whether one texture edge visibly disagrees
with the texture next to it. The first implementation keeps neighbor context
optional so current download scoring remains simple and deterministic.

Structured details identify the worst edge, per-edge risk values, border
gradient values, and whether neighbor comparison contributed to the result.

## Backend Contract

The first implementation keeps the current direct function calls and does not
add OpenCV, scikit-image, ONNX Runtime, OpenVINO, or ML model loading. The
durable future backend contract is:

- input: sampled RGB image array plus optional scoring context;
- output: `ProviderScoreMetrics` with structured detail fields;
- default backend: deterministic NumPy/Pillow metrics, always available;
- future optional backends: OpenCV/scikit-image/ONNX/OpenVINO implementations
  that can be installed and selected without changing the default runtime.

The first implementation adds the data shapes needed for that contract, but it
does not add runtime backend selection. A later optional-backend issue can add
an explicit `heuristic` default and fallback behavior after there is a concrete
non-default backend to test.

## Data Flow

Downloaded or assembled texture images already pass through provider scoring
from `O4_Imagery_Utils.py`. That flow remains unchanged:

1. sample image to a bounded RGB NumPy array;
2. compute provider score metrics;
3. clamp metrics and compute global provider quality;
4. log one structured `Provider imagery score` event with all metric details.

The scoring functions must remain deterministic and independent of network
access, X-Plane installs, GDAL command-line tools, or provider servers.

## Error Handling

Image scoring is diagnostic and must not break a texture download that otherwise
succeeded. Invalid or undersized arrays return conservative zero-risk details
instead of raising avoidable exceptions. Real programming errors must
not be swallowed silently during tests.

Future optional backend failures must be logged and fall back to the heuristic
backend. The default backend in this task has no optional dependency failure
mode.

## Tests

Unit tests should use synthetic PIL images and NumPy arrays. Required behaviors:

- a uniform low-risk image remains excellent;
- small bright low-saturation coverage under 5 percent does not materially
  penalize cloud score;
- dense white cloud coverage above 5 percent increases cloud risk;
- blue-sky-like bright pixels are excluded from cloud coverage;
- low-variance haze increases veil/cloud risk;
- one problematic edge increases seam risk and identifies that edge;
- abrupt border gradients increase seam risk;
- optional neighbor-edge mismatch increases seam risk when context is supplied;
- metric details appear in structured score context;
- existing provider scoring integration tests still log a usable global score.

The implementation must follow the repository's `unittest` rule and write
failing tests before production changes.

## Documentation and Tracking

`TODO.md` should be updated only after implementation and verification pass.
If a GitHub issue exists for TODO-041, the final work should comment with
implementation evidence and close the issue when acceptance criteria pass. If no
issue exists, that absence should be recorded in final evidence or a new issue
should be created according to the repository tracking rules.
