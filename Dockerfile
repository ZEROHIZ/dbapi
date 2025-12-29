FROM node:lts AS BUILD_IMAGE

WORKDIR /app

COPY . /app

# 使用淘宝源加速构建
RUN yarn install --registry https://registry.npmmirror.com/ --ignore-engines && yarn run build

FROM node:lts-alpine

# 设置时区为上海，确保 Cron 任务每天 0 点（北京时间）准时执行
RUN apk add --no-cache tzdata
ENV TZ=Asia/Shanghai

WORKDIR /app

# 复制构建产物
COPY --from=BUILD_IMAGE /app/configs /app/configs
COPY --from=BUILD_IMAGE /app/package.json /app/package.json
COPY --from=BUILD_IMAGE /app/dist /app/dist
COPY --from=BUILD_IMAGE /app/public /app/public
COPY --from=BUILD_IMAGE /app/node_modules /app/node_modules

# 创建数据目录并赋予权限 (确保 Node 进程可以写入)
RUN mkdir -p /app/data && chmod 777 /app/data

# 声明数据卷，提示用户挂载此目录以持久化账号数据
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["npm", "start"]
