def factorial(n):
    if n < 0:
        raise ValueError("n must be non-negative")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def main():
    print("Hello from my-project!")
    print(factorial(5))


if __name__ == "__main__":
    main()
