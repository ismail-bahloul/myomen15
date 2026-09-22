// A minimal CUDA load for the dGPU clock-lock test (dgpu-control.md).
// Holds the GPU at 100% so clocks and power can be read back under the lock.
//   nvcc -O2 -o gpuload gpuload.cu
//   ./gpuload &            # runs until killed
//   sudo nvidia-smi --lock-gpu-clocks=300,1000
#include <cuda_runtime.h>

__global__ void spin(float* a, int n, int iters)
{
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    float x = a[i];
    for (int k = 0; k < iters; k++)
        x = fmaf(x, 1.0000001f, 0.0000001f);
    a[i] = x;
}

int main(void)
{
    int n = 1 << 22;
    float* d;
    cudaMalloc(&d, (size_t)n * 4);
    cudaMemset(d, 0, (size_t)n * 4);
    for (;;)
        spin<<<n / 256, 256>>>(d, n, 20000);
}
