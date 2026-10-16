ARG PHP_VERSION=8.4
FROM php:${PHP_VERSION}-apache

# PHP extensions for Laravel
RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    zlib1g-dev \
    libicu-dev \
    g++ \
    libbz2-dev \
    libzip-dev \
    libxml2-dev \
    ssh \
    gnupg2 \
    git \
    libpq-dev \
    && docker-php-ext-install -j$(nproc) zip \
    pdo_mysql \
    pdo_pgsql \
    opcache \
    bcmath \
    bz2 \
    soap \
    && docker-php-ext-configure gd --with-freetype=/usr/include/ --with-jpeg=/usr/include/ \
    && docker-php-ext-install -j$(nproc) gd \
    && docker-php-ext-configure intl \
    && docker-php-ext-install -j$(nproc) intl \
    && docker-php-ext-configure opcache --enable-opcache \
    && docker-php-ext-install -j$(nproc) opcache \
    && pecl install redis \
    && docker-php-ext-enable redis \
    && rm -rf /var/lib/apt/lists/*

# Opcache & PHP config
COPY conf/ /usr/local/etc/php/conf.d/

# Composer
COPY --from=composer /usr/bin/composer /usr/bin/composer

# Node.js
RUN curl -sL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && apt-get purge -y g++ gnupg2 \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Apache: document root, rewrite, hide server info
ENV APACHE_DOCUMENT_ROOT=/var/www/html/public
RUN sed -ri -e 's!/var/www/html!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/sites-available/*.conf \
    && sed -ri -e 's!/var/www/!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/apache2.conf /etc/apache2/conf-available/*.conf \
    && sed -ri -e 's!AllowOverride None!AllowOverride All!g' /etc/apache2/apache2.conf \
    && sed -ri -e 's!ServerSignature On!ServerSignature Off!g' /etc/apache2/apache2.conf /etc/apache2/conf-available/*.conf \
    && sed -ri -e 's!ServerTokens OS!ServerTokens Prod!g' /etc/apache2/apache2.conf /etc/apache2/conf-available/*.conf \
    && a2enmod rewrite

# Minimal entrypoint: forward the development server command
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Dev: switch to www-data with login shell
RUN chown -R www-data:www-data /var/www/ \
    && sed -ri -e 's!www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin!www-data:x:33:33:www-data:/var/www:/bin/bash!g' /etc/passwd
USER www-data
RUN npm config set prefix '~/.local/' \
    && mkdir -p ~/.local/bin \
    && echo 'export PATH=~/.local/bin:$PATH' >> ~/.bashrc

ENTRYPOINT ["entrypoint.sh"]
CMD ["apache2-foreground"]
