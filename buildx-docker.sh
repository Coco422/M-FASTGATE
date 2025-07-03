docker buildx build --platform linux/arm64 --load -t m-fastgate:arm64-v0.3.0 . && docker save m-fastgate:arm64-v0.3.0 -o m-fastgate-arm64-v0.3.0.tar

docker tag m-fastgate:arm64-v0.3.0 hub.szmckj.cn/miniai/m-fastgate:arm64-v0.3.0

docker push hub.szmckj.cn/miniai/m-fastgate:arm64-v0.3.0 